"""Dispatches the generation of an exercise set to the matching module."""

import random
from datetime import datetime, timedelta, timezone

from celery.exceptions import SoftTimeLimitExceeded
from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.limits import (
    AIA_TOOL_BUSY_MAX_MINUTES, AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT, PROVIDER_BUSY_WAIT_SECONDS,
)
from src.services.upstream_errors import is_upstream_busy
from src.features.ai_assistant.tasks._helpers import (
    LEARNING_TOOLS,
    _get_llm_client,
    learning_tools_language,
    tool_output_language,
)
from src.services.aia_adaptive_tools import build_adaptive_tool_suffix
from src.features.ai_assistant.repository.grammar_topics import catalog_entry
from src.services.aia_grammar_formats import clean_kinds
from src.services.aia_grammar_topic import derive_topic

from src.features.ai_assistant.tasks._context_budget import exercise_context_budget
from src.features.ai_assistant.tasks._instruction import NONE, Resolution, prompt_block
from src.features.ai_assistant.tasks._instruction import resolve as resolve_instruction
from src.features.ai_assistant.tasks._warten import platz_nachfuehren
from src.features.ai_assistant.tasks.language_training._context import (
    build_context_from_chunks,
    build_source_context,
    label_for_sources,
    coverage_rule,
)
from src.features.ai_assistant.tasks.language_training._dedup import (
    drop_repeats,
    seen_by_user,
)
from src.features.ai_assistant.tasks.language_training._pool import (
    pool_level,
    store as store_in_pool,
    take as take_from_pool,
    title_from_items as pool_title,
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


# Stands in the title column until the generation call or the pool names the set.
_PLATZHALTER = "Wird generiert…"

# A set that hits the time limit this often is too big and not merely waiting.
_ZEITGRENZE_ANLAEUFE = 3


@celery_app.task(bind=True, name="aia.generate_exercise_set", queue="aia",
                 soft_time_limit=AIA_TOOL_SOFT_TIME_LIMIT, time_limit=AIA_TOOL_TIME_LIMIT)
@observe(name="aia-exercise-set")
def run_generate_exercise_set(self, set_id: int, workspace_id: int, tool: str,
                              mode: str, count: int, source_uuid: str | None = None,
                              source_uuids: list[str] | None = None,
                              locale: str = "de", anlauf: int = 0, _aia_job_uuid: str | None = None):
    """Generates the exercises of a set, the language follows the course."""
    erstellt = None
    # A requeued run takes the seat along and gives it back itself.
    platz_weiter = False
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
        erstellt = ex_set.get("created_at")

        # The exercise language follows the course, not the person's interface.
        locale, language = (learning_tools_language() if tool in LEARNING_TOOLS
                            else tool_output_language(workspace_id))

        client, model, _ = _get_llm_client()

        # The exercises are tuned to the stored language level.
        adaptive_suffix = build_adaptive_tool_suffix(user_id)

        # The vocabulary cloze goes its own way, one sentence is one exercise.
        if tool == "wortschatz":
            run_cloze_set(set_id, ex_set, user_id, count, client, model,
                          language, adaptive_suffix,
                          source_uuids or ([source_uuid] if source_uuid else []))
            return

        # Names the titles already taken so a second set is called something else.
        title_avoidance = build_title_avoidance_block(workspace_id, tool)

        items: list[dict] = []
        title = _PLATZHALTER
        # Set-level text (instruction + worked example). Only the grammar tool fills it.
        header: dict | None = None
        # Stays None in glossary mode, which has no sources and therefore no sections.
        ctx = None
        # The person's instruction, empty when there is none or it missed the material.
        anweisung = ""
        # True when the material is the found spots instead of the sweep.
        gezielt = False
        # The pool only serves runs without an instruction, its items were made without one.
        mit_vorrat = False

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

            # The instruction decides the way before the pool is asked.
            gewuenscht = ex_set.get("user_instruction") or ""
            wahl = (resolve_instruction(workspace_id, _source_ids(uuids), gewuenscht,
                                        exercise_context_budget(count))
                    if gewuenscht.strip() else Resolution("", None, False, NONE))
            # Written anew on every run, so a retry that hits the material clears an old miss.
            if gewuenscht.strip():
                db.set_instruction_unmatched("aia_exercise_sets", set_id, wahl.unmatched)
            anweisung = wahl.text
            gezielt = wahl.chunks is not None

            # Pool first, then the model, only unseen items are taken.
            level = pool_level(adaptive_suffix, user_id)
            # The grammar exercise splits its pool by topic as well.
            topic_id = ex_set.get("grammar_topic_id") if tool == "grammatik" else None
            # Clean the formats again, an old set can carry dead codes.
            kinds = (clean_kinds(ex_set.get("grammar_kinds"))
                     if tool == "grammatik" else None)
            mit_vorrat = uses_pool(tool, mode) and not anweisung
            if mit_vorrat:
                items = take_from_pool(uuids, tool, level, user_id, count, topic_id,
                                       kinds=kinds)
                if items:
                    logger.info("KI Tutor: set {} nimmt {} von {} aus dem Vorrat",
                                set_id, len(items), count)

            zu_erzeugen = count - len(items)
            if zu_erzeugen <= 0:
                # The pool was enough, only the title is missing.
                ctx = None
            elif gezielt:
                ctx = build_context_from_chunks(uuids, wahl.chunks)
                if ctx is None:
                    db.fail_exercise_set(set_id)
                    return
            else:
                ctx = build_source_context(uuids, tool, count=zu_erzeugen)
                if ctx is None and not items:
                    db.fail_exercise_set(set_id)
                    return

        if mode == "source" and ctx is not None:

            gtype = None
            if tool == "grammatik":
                # The topic is read again, the job can run long after the request.
                topic = db.get_grammar_topic(ex_set.get("grammar_topic_id"))
                if not topic:
                    db.fail_exercise_set(set_id)
                    return
                spec = db.get_topic_spec(topic["id"], locale)
                if not spec:
                    # First use in this language, rule and example hang off it.
                    derived = derive_topic(client, model, topic["name"], language)
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
                """One generation run against a context, returns exercises, title and header."""
                # Only equally sized numbered sections with a quota make the model use them all.
                # Found spots carry no quota, the topic may sit in one source alone.
                cov = "" if gezielt else coverage_rule(from_ctx, how_many)
                shared = dict(locale=locale, language=language,
                              adaptive_suffix=adaptive_suffix,
                              title_avoidance=title_avoidance, coverage=cov)
                if tool == "flashcards":
                    got, name = generate_flashcards_from_source(
                        client, model, from_ctx, how_many, **shared)
                    return got, name, None
                if tool == "karteikarten":
                    got, name = generate_cards_from_source(
                        client, model, from_ctx, how_many,
                        instruction=prompt_block(anweisung, narrowed=gezielt), **shared)
                    return got, name, None
                if tool == "grammatik":
                    # One call, the chosen formats mixed evenly.
                    return generate_grammar_from_source(
                        client, model, from_ctx, gtype, how_many, kinds=kinds, **shared)
                got, name = generate_mc_from_source(
                    client, model, from_ctx, how_many,
                    instruction=prompt_block(anweisung), **shared)
                return got, name, None

            # One call per set, a shortfall is filled from the pool or the model's repeats.
            neu, title, header = generate(ctx, zu_erzeugen)

            # Whatever this person already had is dropped.
            gehabt = seen_by_user(user_id, tool)
            # What the model repeated stays at hand, it fills the set once the material is used up.
            schon_gehabt: list[dict] = []
            if neu:
                vorher = neu
                neu, wiederholt = drop_repeats(neu, gehabt + [i.get("front", "") for i in items])
                schon_gehabt += [i for i in vorher if all(i is not k for k in neu)]
                if wiederholt:
                    logger.info("KI Tutor: set {} hat {} Wiederholungen aussortiert",
                                set_id, wiederholt)

            # Truly nothing new left in the pool or from the model: a repeat still
            # beats a set that stays short.
            fehlt = zu_erzeugen - len(neu)
            aufgefuellt = 0
            if fehlt > 0 and mit_vorrat:
                wiederholt = take_from_pool(
                    uuids, tool, level, user_id, fehlt, topic_id,
                    exclude_ids=[i["pool_item_id"] for i in items if i.get("pool_item_id")],
                    kinds=kinds, ignore_seen=True,
                )
                if wiederholt:
                    # Must not collide with what the model just generated either.
                    wiederholt, _ = drop_repeats(wiederholt, [i.get("front", "") for i in neu])
                if wiederholt:
                    logger.info(
                        "KI Tutor: set {} füllt {} von {} fehlenden Plätzen mit bereits "
                        "gesehenen Aufgaben, Vorrat und Modell reichen nicht mehr",
                        set_id, len(wiederholt), fehlt,
                    )
                    items = items + wiederholt
                    aufgefuellt = len(wiederholt)

            # Material used up: the person gets repeats rather than a set that fails.
            fehlt = zu_erzeugen - len(neu) - aufgefuellt
            if fehlt > 0 and schon_gehabt:
                nochmal, _ = drop_repeats(schon_gehabt, [i.get("front", "") for i in items + neu])
                nochmal = nochmal[:fehlt]
                if nochmal:
                    logger.info("KI Tutor: set {} füllt {} von {} fehlenden Plätzen mit Wiederholungen, "
                                "das Material ist ausgeschöpft", set_id, len(nochmal), fehlt)
                    for item in nochmal:
                        item.pop("_kind", None)
                    items = items + nochmal

            # Store them so the next call gets them for free, the name comes along
            # so a later set drawn purely from the pool needs no call to be named.
            if neu and mit_vorrat:
                store_in_pool(neu, ctx, tool, level, topic_id, set_title=title)

            # The presentation format now lives in the pool and has no place in the set.
            for item in neu:
                item.pop("_kind", None)

            items = items + neu

        # The glossary path only compares inside the set, wanted repetitions stay.
        if items and mode == "glossary":
            items, _ = drop_repeats(items, [])

        if not items:
            db.fail_exercise_set(set_id)
            return

        # The name comes out of the generation call itself, see _variation. Only a set
        # drawn entirely from the pool never had one and inherits it from its exercises,
        # falling back to the source for what was pooled before the name was stored.
        if title == _PLATZHALTER:
            title = (pool_title(items)
                     or label_for_sources(source_uuids or ([source_uuid] if source_uuid else []))
                     or title)
        try:
            title = resolve_set_title(workspace_id, tool, title)
        except Exception as e:
            logger.warning("KI Tutor: set {} keeps its provisional title: {}", set_id, e)

        db.finalize_exercise_set(set_id, title, items, header=header, user_id=user_id)
        logger.info("KI Tutor: exercise set {} generated ({} items)", set_id, len(items))
        if mode == "source" and len(items) < count:
            # A set still too short after the top-up is logged, source mode only.
            logger.warning("KI Tutor: set {} bleibt bei {} von {} bestellten Aufgaben",
                           set_id, len(items), count)

    except Exception as e:
        if _wieder_einreihen(e, erstellt, anlauf, [set_id, workspace_id, tool, mode, count],
                             {"source_uuid": source_uuid, "source_uuids": source_uuids,
                              "locale": locale, "_aia_job_uuid": _aia_job_uuid}):
            platz_weiter = True
            return
        logger.error("KI Tutor: exercise set {} generation failed: {}", set_id, e)
        db.fail_exercise_set(set_id)
    finally:
        if _aia_job_uuid and not platz_weiter:
            try:
                from src.features.ai_assistant.scheduling.service import on_complete
                on_complete(_aia_job_uuid)
            except Exception as fehler:
                logger.error("KI Tutor: exercise_set dispatch on_complete failed: {}", fehler)


def _wieder_einreihen(e: Exception, erstellt, anlauf: int, args: list, kwargs: dict) -> bool:
    """Puts the set back in the queue when only the provider was too slow or too busy."""
    from src.features.ai_assistant.tasks._retry import _soft_deadline
    # The SDK hides an expired deadline behind a connection error, that is no busy provider.
    if isinstance(e, SoftTimeLimitExceeded) or _soft_deadline(e) is not None:
        if anlauf >= _ZEITGRENZE_ANLAEUFE:
            return False
    elif not is_upstream_busy(e):
        return False
    jetzt = datetime.now(timezone.utc).replace(tzinfo=None)
    if erstellt and jetzt - erstellt > timedelta(minutes=AIA_TOOL_BUSY_MAX_MINUTES):
        return False
    warte = random.uniform(*PROVIDER_BUSY_WAIT_SECONDS)
    try:
        ergebnis = run_generate_exercise_set.apply_async(
            args=args, kwargs={**kwargs, "anlauf": anlauf + 1}, countdown=warte)
    except Exception as fehler:
        logger.error("KI Tutor: set {} could not be requeued: {}", args[0], fehler)
        return False
    platz_nachfuehren(kwargs, ergebnis)
    logger.warning("KI Tutor: set {} waits {:.0f} s for the provider ({}), run {}",
                   args[0], warte, type(e).__name__, anlauf + 2)
    return True


def _source_ids(uuids: list[str]) -> list[int]:
    """The ids behind the chosen sources, an unknown one is skipped."""
    ids = []
    for suuid in uuids:
        source = db.get_aia_source(suuid)
        if source and source.get("id"):
            ids.append(source["id"])
    return ids


__all__ = ["run_generate_exercise_set"]
