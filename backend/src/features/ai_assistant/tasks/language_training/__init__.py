"""KI-Assistent Celery-Task: Exercise-Set-Generierung.

Dispatcht je nach `mode` (glossary/source) und `tool`
(flashcards/karteikarten/quiz/grammatik/hoerverstehen) an die passenden
Handler-Module."""

from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.limits import AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT
from src.features.ai_assistant.tasks._helpers import _get_llm_client
from src.services.aia_adaptive_tools import build_adaptive_tool_suffix
from src.features.ai_assistant.repository.grammar_topics import catalog_entry
from src.services.aia_grammar_check import normalize
from src.services.aia_grammar_topic import derive_topic

from src.features.ai_assistant.tasks.language_training._context import (
    build_source_context,
    coverage_rule,
    missing_section_uuids,
    per_section_quota,
    rebalance_to_count,
    remap_sections,
)
from src.features.ai_assistant.tasks.language_training._glossary import generate_from_glossary
from src.features.ai_assistant.tasks.language_training._source_cards import (
    generate_cards_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_flashcards import (
    generate_flashcards_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_grammar import (
    generate_grammar_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_listening import (
    generate_listening_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_mc import generate_mc_from_source
from src.features.ai_assistant.tasks.language_training._variation import (
    build_title_avoidance_block,
    resolve_set_title,
)


@celery_app.task(bind=True, name="aia.generate_exercise_set", queue="aia",
                 soft_time_limit=AIA_TOOL_SOFT_TIME_LIMIT, time_limit=AIA_TOOL_TIME_LIMIT)
@observe(name="aia-exercise-set")
def run_generate_exercise_set(self, set_id: int, workspace_id: int, tool: str,
                              mode: str, count: int, source_uuid: str | None = None,
                              source_uuids: list[str] | None = None,
                              locale: str = "de"):
    """Generate items for an exercise set (flashcards/karteikarten/quiz/grammatik).

    `locale` controls the RAG sentinel string for source-cards generation
    (the AIA_SYSTEM_RAG prompt builder). Defaults to 'de' so older queued
    tasks keep working.
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

        client, model, _ = _get_llm_client()

        # Pitch the generated items at the learner's stored CEFR level, exactly as
        # the chat does. Empty string when the learner has no level yet, so the
        # tools keep their shipped register.
        adaptive_suffix = build_adaptive_tool_suffix(user_id, workspace_id)

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

        if mode == "glossary":
            result = generate_from_glossary(client, model, workspace_id, user_id, tool, count,
                                            locale=locale, adaptive_suffix=adaptive_suffix)
            if result is None:
                db.fail_exercise_set(set_id)
                return
            items, title = result

        elif mode == "source":
            uuids = source_uuids or ([source_uuid] if source_uuid else [])
            if not uuids:
                db.fail_exercise_set(set_id)
                return
            ctx = build_source_context(uuids, tool, count=count)
            if ctx is None:
                db.fail_exercise_set(set_id)
                return

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
                    derived = derive_topic(client, model, topic["name"], locale)
                    if not derived:
                        logger.warning(
                            "KI Tutor: Thema {!r} liess sich in {} nicht ausarbeiten",
                            topic["name"], locale,
                        )
                        db.fail_exercise_set(set_id)
                        return
                    spec = db.save_topic_spec(
                        topic["id"], locale, derived["rule"], derived["examples"])
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
                shared = dict(locale=locale, adaptive_suffix=adaptive_suffix,
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
                    # Ein Aufruf, vier Formate gleichmässig gemischt.
                    return generate_grammar_from_source(
                        client, model, from_ctx, gtype, how_many, **shared)
                if tool == "hoerverstehen":
                    # Läuft wie das Quiz über den ganzen Kontext, nur mit anderen
                    # Fragearten. Das Sprachniveau entscheidet, ob Schlussfolgerungen
                    # dabei sind, deshalb kommt es hier zusätzlich mit.
                    got, name = generate_listening_from_source(
                        client, model, from_ctx, how_many,
                        level=db.get_user_language_level(user_id)["language_level"],
                        **shared)
                    return got, name, None
                got, name = generate_mc_from_source(
                    client, model, from_ctx, how_many, **shared)
                return got, name, None

            items, title, header = generate(ctx, count)

            # Did every section actually get used? Measured: the grammar tool served all
            # five on its own, the quiz skipped the last one in both runs. So the sections
            # that came up empty get one more run of their own, and only then.
            if items and len(ctx.sections) > 1:
                gap_uuids = missing_section_uuids(items, ctx)
                if gap_uuids:
                    logger.info(
                        "KI Tutor: set {} skipped {} of {} sections, topping up",
                        set_id, len(gap_uuids), len(ctx.sections),
                    )
                    need = per_section_quota(len(ctx.sections), count) * len(gap_uuids)
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
                                seen_fronts = {normalize(i["front"]) for i in items}
                                extra = [i for i in extra
                                         if normalize(i["front"]) not in seen_fronts]
                                items = rebalance_to_count(items + extra, count)
                    except Exception as e:
                        logger.warning(
                            "KI Tutor: set {} top-up failed, keeping the {} items already "
                            "generated: {}", set_id, len(items), e,
                        )

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

    except Exception as e:
        logger.error("KI Tutor: exercise set {} generation failed: {}", set_id, e)
        db.fail_exercise_set(set_id)


__all__ = ["run_generate_exercise_set"]
