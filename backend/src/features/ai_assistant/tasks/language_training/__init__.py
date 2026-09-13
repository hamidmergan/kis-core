"""Dispatches the generation of an exercise set to the matching module."""

from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.limits import AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT
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

from src.features.ai_assistant.tasks.language_training._context import (
    build_source_context,
    quota_fits,
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


# This many top-up rounds, at most two.
_NACHSCHLAG_RUNDEN = 2


@celery_app.task(bind=True, name="aia.generate_exercise_set", queue="aia",
                 soft_time_limit=AIA_TOOL_SOFT_TIME_LIMIT, time_limit=AIA_TOOL_TIME_LIMIT)
@observe(name="aia-exercise-set")
def run_generate_exercise_set(self, set_id: int, workspace_id: int, tool: str,
                              mode: str, count: int, source_uuid: str | None = None,
                              source_uuids: list[str] | None = None,
                              locale: str = "de"):
    """Generates the exercises of a set, the language follows the course."""
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
        title = "Wird generiert…"
        # Set-level text (instruction + worked example). Only the grammar tool fills it.
        header: dict | None = None
        # Stays None in glossary mode, which has no sources and therefore no sections.
        ctx = None
        # Only set in source mode, glossary mode has nothing to top up.
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

            # Pool first, then the model, only unseen items are taken.
            level = pool_level(adaptive_suffix, user_id)
            # The grammar exercise splits its pool by topic as well.
            topic_id = ex_set.get("grammar_topic_id") if tool == "grammatik" else None
            # Clean the formats again, an old set can carry dead codes.
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
                # The pool was enough, only the title is missing.
                ctx = None
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
                    # One call, the chosen formats mixed evenly.
                    return generate_grammar_from_source(
                        client, model, from_ctx, gtype, how_many, kinds=kinds, **shared)
                got, name = generate_mc_from_source(
                    client, model, from_ctx, how_many, **shared)
                return got, name, None

            refill = generate
            # Only the shortfall is generated, the pool is already in items.
            neu, title, header = generate(ctx, zu_erzeugen)

            # Sections left empty get a run of their own, and only those.
            if neu and quota_fits(ctx, zu_erzeugen):
                gap_uuids = missing_section_uuids(neu, ctx)
                if gap_uuids:
                    logger.info(
                        "KI Tutor: set {} skipped {} of {} sections, topping up",
                        set_id, len(gap_uuids), len(ctx.sections),
                    )
                    need = per_section_quota(len(ctx.sections), zu_erzeugen) * len(gap_uuids)
                    # The top-up is an improvement, whatever is finished gets saved.
                    try:
                        gap_ctx = build_source_context(gap_uuids, tool, count=need)
                        if gap_ctx is not None:
                            extra, _, _ = generate(gap_ctx, need)
                            if extra:
                                # The top-up numbers its own sections, that has to be undone before merging.
                                remap_sections(extra, gap_ctx, ctx)
                                # Across the run boundary no run sorts out its own duplicates.
                                extra, _ = drop_repeats(
                                    extra, [i.get("front", "") for i in neu])
                                neu = rebalance_to_count(neu + extra, zu_erzeugen)
                    except Exception as e:
                        logger.warning(
                            "KI Tutor: set {} top-up failed, keeping the {} items already "
                            "generated: {}", set_id, len(neu), e,
                        )

            # Whatever this person already had is dropped.
            gehabt = seen_by_user(user_id, tool)
            if neu:
                neu, wiederholt = drop_repeats(neu, gehabt + [i.get("front", "") for i in items])
                if wiederholt:
                    logger.info("KI Tutor: set {} hat {} Wiederholungen aussortiert",
                                set_id, wiederholt)

            # Top up until the requested number is reached.
            for _ in range(_NACHSCHLAG_RUNDEN):
                fehlt = zu_erzeugen - len(neu)
                if fehlt <= 0:
                    break
                logger.info("KI Tutor: set {} hat {} von {} Aufgaben, bestellt {} nach",
                            set_id, len(neu), zu_erzeugen, fehlt)
                try:
                    mehr, _, _ = generate(ctx, fehlt)
                except Exception as e:
                    # The top-up is an improvement, whatever is finished gets saved.
                    logger.warning(
                        "KI Tutor: set {} behaelt seine {} eigenen Aufgaben, "
                        "Nachschlag fehlgeschlagen: {}", set_id, len(neu), e,
                    )
                    break
                if mehr:
                    mehr, _ = drop_repeats(
                        mehr, gehabt + [i.get("front", "") for i in items + neu])
                if not mehr:
                    # Not a single new exercise, asking further only costs requests.
                    break
                neu = rebalance_to_count(neu + mehr, zu_erzeugen)

            # Truly nothing new left in the pool or from the model: a repeat still
            # beats a set that stays short.
            fehlt = zu_erzeugen - len(neu)
            if fehlt > 0 and uses_pool(tool, mode):
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

            # Store them so the next call gets them for free.
            if neu and uses_pool(tool, mode):
                store_in_pool(neu, ctx, tool, level, topic_id)

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

        # The title is built here from the finished exercises, not in the generation call.
        try:
            title = resolve_set_title(client, model, workspace_id, tool, title, items)
        except Exception as e:
            logger.warning("KI Tutor: set {} keeps its provisional title: {}", set_id, e)

        db.finalize_exercise_set(set_id, title, items, header=header, user_id=user_id)
        logger.info("KI Tutor: exercise set {} generated ({} items)", set_id, len(items))
        if mode == "source" and len(items) < count:
            # A set still too short after the top-up is logged, source mode only.
            logger.warning("KI Tutor: set {} bleibt bei {} von {} bestellten Aufgaben",
                           set_id, len(items), count)

    except Exception as e:
        logger.error("KI Tutor: exercise set {} generation failed: {}", set_id, e)
        db.fail_exercise_set(set_id)


__all__ = ["run_generate_exercise_set"]
