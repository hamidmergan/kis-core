"""KI-Assistent Celery-Task: Exercise-Set-Generierung.

Dispatcht je nach `mode` (glossary/source) und `tool`
(flashcards/karteikarten/quiz/grammatik) an die passenden
Handler-Module."""

from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.limits import AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT
from src.features.ai_assistant.tasks._helpers import _get_llm_client, tool_output_language
from src.services.aia_adaptive_tools import build_adaptive_tool_suffix
from src.features.ai_assistant.repository.grammar_topics import catalog_entry
from src.services.aia_grammar_formats import clean_kinds
from src.services.aia_grammar_topic import derive_task_lines, derive_topic

from src.features.ai_assistant.tasks.language_training._context import (
    build_source_context,
    coverage_rule,
    missing_section_uuids,
    per_section_quota,
    rebalance_to_count,
    remap_sections,
)
from src.features.ai_assistant.tasks.language_training._dedup import (
    drop_repeats,
    seen_by_user,
)
from src.features.ai_assistant.tasks.language_training._pool import (
    pool_level,
    store as store_in_pool,
    take as take_from_pool,
    uses_pool,
)
from src.features.ai_assistant.tasks.language_training._glossary import generate_from_glossary
from src.features.ai_assistant.tasks.language_training._source_cards import (
    generate_cards_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_cloze import run_cloze_set
from src.features.ai_assistant.tasks.language_training._source_flashcards import (
    generate_flashcards_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_grammar import (
    generate_grammar_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_mc import generate_mc_from_source
from src.features.ai_assistant.tasks.language_training._variation import (
    build_title_avoidance_block,
    resolve_set_title,
)


# So oft wird nachbestellt, bis die verlangte Anzahl steht. Zwei Runden und nicht mehr.
# Eine Runde, die keine einzige neue Aufgabe bringt, beendet den Nachschlag ohnehin sofort, denn dann hat das Dokument
# nichts mehr herzugeben und ein kuerzerer Satz ist die ehrliche Antwort.
_NACHSCHLAG_RUNDEN = 2


@celery_app.task(bind=True, name="aia.generate_exercise_set", queue="aia",
                 soft_time_limit=AIA_TOOL_SOFT_TIME_LIMIT, time_limit=AIA_TOOL_TIME_LIMIT)
@observe(name="aia-exercise-set")
def run_generate_exercise_set(self, set_id: int, workspace_id: int, tool: str,
                              mode: str, count: int, source_uuid: str | None = None,
                              source_uuids: list[str] | None = None,
                              locale: str = "de"):
    """Generate items for an exercise set (flashcards/karteikarten/quiz/grammatik).

    `locale` kommt vom Aufrufer, wird hier aber sofort durch die Unterrichtssprache des
    Kursraums ersetzt: was der Lernende zu sehen bekommt, folgt dem Kurs und nicht der
    Sprachwahl in seinem Kopf der Seite.
    """
    try:
        workspace = db.get_aia_workspace_by_id(workspace_id)
        if not workspace:
            db.fail_exercise_set(set_id)
            return

        ex_set = db.get_exercise_set_with_items(set_id)
        if not ex_set:
            db.fail_exercise_set(set_id)
            return
        user_id = ex_set["user_id"]

        # Die Sprache der Aufgaben haengt am Kursraum, nicht an der Oberflaeche der
        # Person. `locale` wird hier bewusst ueberschrieben: alles weiter unten, was den
        # Lernenden erreicht (Anweisungszeile, Richtig/Falsch-Beschriftung, Grammatikregel
        # und Musterbeispiel), soll in der Unterrichtssprache stehen und nicht in der
        # Sprache, auf die jemand seine Knoepfe gestellt hat.
        locale, language = tool_output_language(workspace_id)

        client, model, _ = _get_llm_client()

        # Pitch the generated items at the learner's stored CEFR level, exactly as
        # the chat does. Empty string when the learner has no level yet, so the
        # tools keep their shipped register.
        adaptive_suffix = build_adaptive_tool_suffix(user_id, workspace_id)

        # Der Wortschatz-Lückentext geht seinen eigenen Weg und nicht durch die
        # Maschinerie darunter. Ein Set ist bei ihm EINE Aufgabe, es gibt also nichts
        # nachzubestellen, nichts zu entdoppeln und keine Abschnittsquote zu erfüllen.
        # Die drei Schritte hier sind alles, was er braucht.
        if tool == "wortschatz":
            run_cloze_set(set_id, ex_set, user_id, count, client, model,
                          language, adaptive_suffix,
                          source_uuids or ([source_uuid] if source_uuid else []))
            return

        # Names the titles this workspace already uses for this tool, so a second set
        # from the same document does not end up with the same name. Only the title,
        # never the items: those get copied when fed back (see the generator comments).
        title_avoidance = build_title_avoidance_block(workspace_id, tool)

        items: list[dict] = []
        title = "Wird generiert…"
        # Set-level text (instruction + worked example). Only the grammar tool fills it.
        header: dict | None = None
        # Stays None in glossary mode, which has no sources and therefore no sections.
        ctx = None
        # Set in source mode so the duplicate filter below can order a refill. Glossary
        # mode leaves it None: it draws from a finite term list, so a second run has
        # nothing new to offer and the set is simply shorter.
        refill = None

        if mode == "glossary":
            result = generate_from_glossary(client, model, workspace_id, user_id, tool, count,
                                            locale=locale, language=language,
                                            adaptive_suffix=adaptive_suffix)
            if result is None:
                db.fail_exercise_set(set_id)
                return
            items, title = result

        elif mode == "source":
            uuids = source_uuids or ([source_uuid] if source_uuid else [])
            if not uuids:
                db.fail_exercise_set(set_id)
                return

            # Erst der Vorrat, dann das Modell. Was frueher hier schon erzeugt wurde,
            # liegt an der Quelle und steht allen offen; genommen wird nur, was diese
            # Person noch nicht hatte. Reicht das, kostet die ganze Anfrage keinen
            # einzigen Modellaufruf.
            level = pool_level(adaptive_suffix, user_id)
            # Die Grammatik-Uebung haengt zusaetzlich am gewaehlten Thema: aus demselben
            # Text entsteht eine Passiv- oder eine Konjunktiv-Aufgabe. Ihr Vorrat trennt
            # deshalb auch danach. Bei allen anderen Werkzeugen bleibt das Thema leer.
            topic_id = ex_set.get("grammar_topic_id") if tool == "grammatik" else None
            # Die gewaehlten Aufgabenformate. Noch einmal gesaeubert, weil der Satz
            # aelter sein kann als die heutigen Formate: ein Kuerzel, das es nicht mehr
            # gibt, soll den Auftrag nicht schief machen. None heisst gemischt.
            kinds = (clean_kinds(ex_set.get("grammar_kinds"))
                     if tool == "grammatik" else None)
            if uses_pool(tool, mode):
                items = take_from_pool(uuids, tool, level, user_id, count, topic_id,
                                       kinds=kinds)
                if items:
                    logger.info("KI Tutor: set {} nimmt {} von {} aus dem Vorrat",
                                set_id, len(items), count)

            zu_erzeugen = count - len(items)
            if zu_erzeugen <= 0:
                # Der Vorrat hat gereicht. Kein Kontext, kein Aufruf, kein Fegen des
                # Dokuments: der Titel weiter unten ist alles, was noch aussteht.
                ctx = None
            else:
                ctx = build_source_context(uuids, tool, count=zu_erzeugen)
                if ctx is None and not items:
                    db.fail_exercise_set(set_id)
                    return

        if mode == "source" and ctx is not None:

            gtype = None
            if tool == "grammatik":
                # Das Thema wurde beim Anlegen geprüft, es wird hier neu gelesen, weil
                # der Auftrag lange nach der Anfrage laufen kann.
                topic = db.get_grammar_topic(ex_set.get("grammar_topic_id"))
                if not topic:
                    db.fail_exercise_set(set_id)
                    return
                spec = db.get_topic_spec(topic["id"], locale)
                if not spec:
                    # Erste Benutzung in dieser Sprache. Das trifft jeden Kurs, dessen
                    # Thema in einer anderen Sprache angelegt wurde, denn Regel und
                    # Beispiel hängen an der Sprache und nicht am Namen.
                    derived = derive_topic(client, model, topic["name"], language)
                    if not derived:
                        logger.warning(
                            "KI Tutor: Thema {!r} liess sich in {} nicht ausarbeiten",
                            topic["name"], locale,
                        )
                        db.fail_exercise_set(set_id)
                        return
                    spec = db.save_topic_spec(
                        topic["id"], locale, derived["rule"], derived["examples"],
                        derived.get("task_lines"))
                elif not spec.get("task_lines"):
                    # Ausgearbeitet vor den Anweisungszeilen. Ohne diesen Nachschlag
                    # bliebe so ein Thema fuer immer an der Schablone haengen, denn oben
                    # wird nur ausgearbeitet, was noch gar nicht ausgearbeitet ist.
                    #
                    # Regel und Musterpaar bleiben, wie sie sind: der Dozent darf sie im
                    # Formular geaendert haben, und eine Anweisungszeile ist kein Grund,
                    # ihm das zu ueberschreiben.
                    zeilen = derive_task_lines(client, model, topic["name"], language)
                    if zeilen:
                        spec = db.save_topic_spec(
                            topic["id"], locale, spec["rule"], spec["examples"], zeilen)
                gtype = catalog_entry(topic, spec)

            def generate(from_ctx, how_many):
                """One generation run against one context. Returns (items, title, header).

                Wrapped so the top-up below can repeat it against a smaller context
                without duplicating the tool dispatch.
                """
                # Splitting the context budget only puts every source IN the prompt, and
                # not even evenly. It took equal numbered sections plus a stated quota
                # per section to make the model use them all.
                cov = coverage_rule(from_ctx, how_many)
                shared = dict(locale=locale, language=language,
                              adaptive_suffix=adaptive_suffix,
                              title_avoidance=title_avoidance, coverage=cov)
                if tool == "flashcards":
                    got, name = generate_flashcards_from_source(
                        client, model, from_ctx, how_many, **shared)
                    return got, name, None
                if tool == "karteikarten":
                    got, name = generate_cards_from_source(
                        client, model, from_ctx, how_many, **shared)
                    return got, name, None
                if tool == "grammatik":
                    # Ein Aufruf, die gewaehlten Formate gleichmässig gemischt.
                    return generate_grammar_from_source(
                        client, model, from_ctx, gtype, how_many, kinds=kinds, **shared)
                got, name = generate_mc_from_source(
                    client, model, from_ctx, how_many, **shared)
                return got, name, None

            refill = generate
            # Erzeugt wird nur der Fehlbetrag. Was aus dem Vorrat kam, steht schon in
            # ``items`` und wird am Ende davorgestellt.
            neu, title, header = generate(ctx, zu_erzeugen)

            # Did every section actually get used? Measured: the grammar tool served all
            # five on its own, the quiz skipped the last one in both runs. So the sections
            # that came up empty get one more run of their own, and only then.
            if neu and len(ctx.sections) > 1:
                gap_uuids = missing_section_uuids(neu, ctx)
                if gap_uuids:
                    logger.info(
                        "KI Tutor: set {} skipped {} of {} sections, topping up",
                        set_id, len(gap_uuids), len(ctx.sections),
                    )
                    need = per_section_quota(len(ctx.sections), zu_erzeugen) * len(gap_uuids)
                    # Der Nachschlag ist eine Verbesserung und keine Voraussetzung. Er lief
                    # bis 2026-08-05 im selben try wie alles andere und hat ein Set mit 14
                    # fertigen Aufgaben mitgerissen, als sein Aufruf an einer Störung
                    # scheiterte. Was fertig ist, wird gespeichert.
                    try:
                        gap_ctx = build_source_context(gap_uuids, tool, count=need)
                        if gap_ctx is not None:
                            extra, _, _ = generate(gap_ctx, need)
                            if extra:
                                # The top-up numbers its own sections from 1, so its claims
                                # have to be translated back before the two runs are merged.
                                remap_sections(extra, gap_ctx, ctx)
                                # Jeder Lauf sortiert seine eigenen Doppler aus, über die
                                # Laufgrenze hinweg kann er das nicht. Gemessen: derselbe
                                # Satz kam an Position 1 und noch einmal an Position 5.
                                extra, _ = drop_repeats(
                                    extra, [i.get("front", "") for i in neu])
                                neu = rebalance_to_count(neu + extra, zu_erzeugen)
                    except Exception as e:
                        logger.warning(
                            "KI Tutor: set {} top-up failed, keeping the {} items already "
                            "generated: {}", set_id, len(neu), e,
                        )

            # Was diese Person schon einmal bekommen hat, fliegt raus. Der Vorrat filtert
            # das ueber die Verweise, frisch Erzeugtes hat noch keine.
            gehabt = seen_by_user(user_id, tool)
            if neu:
                neu, wiederholt = drop_repeats(neu, gehabt + [i.get("front", "") for i in items])
                if wiederholt:
                    logger.info("KI Tutor: set {} hat {} Wiederholungen aussortiert",
                                set_id, wiederholt)

            # Nachbestellen, bis die verlangte Anzahl steht. Wer zehn Aufgaben anklickt,
            # will zehn, und es ist ihm gleich, warum es neun geworden sind.
            #
            # Genau daran hing der Fehler: einen Nachschlag gab es nur, wenn der
            # Doppler-Filter etwas weggeworfen hatte, und dann genau einen. Die anderen
            # Gruende blieben unbeantwortet -- das Modell liefert von sich aus weniger, und
            # die Pruefungen der Werkzeuge werfen unloesbare Aufgaben weg (die
            # Grammatik-Uebung tut das laufend). Deshalb kam derselbe
            # Auftrag einmal mit zehn und einmal mit neun Aufgaben heraus.
            for _ in range(_NACHSCHLAG_RUNDEN):
                fehlt = zu_erzeugen - len(neu)
                if fehlt <= 0:
                    break
                logger.info("KI Tutor: set {} hat {} von {} Aufgaben, bestellt {} nach",
                            set_id, len(neu), zu_erzeugen, fehlt)
                try:
                    mehr, _, _ = generate(ctx, fehlt)
                except Exception as e:
                    # Der Nachschlag ist eine Verbesserung und keine Voraussetzung. Was
                    # fertig ist, wird gespeichert.
                    logger.warning(
                        "KI Tutor: set {} behaelt seine {} eigenen Aufgaben, "
                        "Nachschlag fehlgeschlagen: {}", set_id, len(neu), e,
                    )
                    break
                if mehr:
                    mehr, _ = drop_repeats(
                        mehr, gehabt + [i.get("front", "") for i in items + neu])
                if not mehr:
                    # Keine einzige neue Aufgabe. Das Dokument hat nichts mehr, weiter zu
                    # fragen kostet nur Anfragen.
                    break
                neu = rebalance_to_count(neu + mehr, zu_erzeugen)

            # Einlagern, damit der naechste Aufruf sie geschenkt bekommt. Setzt die
            # Vorrats-id an den Aufgaben, die untergebracht werden konnten.
            if neu and uses_pool(tool, mode):
                store_in_pool(neu, ctx, tool, level, topic_id)

            # Die Darreichungsform hat ihren Zweck erfuellt, sie steht jetzt im Vorrat.
            # Im fertigen Satz hat sie nichts verloren, dort traegt jede Aufgabe ihre
            # Anweisung schon selbst.
            for item in neu:
                item.pop("_kind", None)

            items = items + neu

        # Der Glossar-Weg entscheidet VOR der Erzeugung, welche Begriffe drankommen:
        # frische zuerst, aufgefuellt wird mit schon benutzten (siehe ``_pick_terms``).
        # Der Vergleich mit der Vergangenheit stand bis 2026-08-12 hier und wuerde jetzt
        # genau die gewollten Wiederholungen wieder wegwerfen.
        #
        # Was bleibt, ist der Blick in den Satz selbst. Mit leerer Vergangenheitsliste
        # vergleicht ``drop_repeats`` die Aufgaben nur untereinander. Zwei verschiedene
        # Begriffe koennen dieselbe Frage erzeugen, und zwei gleiche Karten nebeneinander
        # sind ein sichtbarer Fehler.
        if items and mode == "glossary":
            items, _ = drop_repeats(items, [])

        if not items:
            db.fail_exercise_set(set_id)
            return

        # The title is decided here, from the finished items, not by the generation call.
        # That call sees the whole document and keeps naming the document, and it is also
        # blind to a set that is still generating, so two sets started seconds apart both
        # came out with the same name. By now the other set is finished and visible.
        #
        # Auch das ist Kosmetik: ein Set mit vorläufigem Namen ist brauchbar, ein
        # verlorenes Set nicht.
        try:
            title = resolve_set_title(client, model, workspace_id, tool, title, items)
        except Exception as e:
            logger.warning("KI Tutor: set {} keeps its provisional title: {}", set_id, e)

        db.finalize_exercise_set(set_id, title, items, header=header)
        logger.info("KI Tutor: exercise set {} generated ({} items)", set_id, len(items))
        if mode == "source" and len(items) < count:
            # Bleibt ein Satz trotz Nachschlag zu kurz, steht das im Protokoll und nicht
            # nur in der Ansicht des Lernenden. Sonst faellt es erst auf, wenn jemand
            # nachzaehlt.
            #
            # Nur im Quellen-Modus: der Glossar-Modus zieht aus einer endlichen
            # Begriffsliste, dort IST der kuerzere Satz die richtige Antwort und keine
            # Warnung wert.
            logger.warning("KI Tutor: set {} bleibt bei {} von {} bestellten Aufgaben",
                           set_id, len(items), count)

    except Exception as e:
        logger.error("KI Tutor: exercise set {} generation failed: {}", set_id, e)
        db.fail_exercise_set(set_id)


__all__ = ["run_generate_exercise_set"]
