"""KI-Assistent Celery-Task: Exercise-Set-Generierung.

Dispatcht je nach `mode` (glossary/source) und `tool`
(flashcards/karteikarten/lueckentext/quiz/vokabeltest) an die passenden
Handler-Module."""

from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.ai_assistant.tasks._helpers import _get_llm_client

from src.features.ai_assistant.tasks.language_training._context import build_source_context
from src.features.ai_assistant.tasks.language_training._glossary import generate_from_glossary
from src.features.ai_assistant.tasks.language_training._source_cards import (
    generate_cards_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_flashcards import (
    generate_flashcards_from_source,
)
from src.features.ai_assistant.tasks.language_training._source_mc import generate_mc_from_source


@celery_app.task(bind=True, name="aia.generate_exercise_set", queue="aia",
                 soft_time_limit=120, time_limit=180)
@observe(name="aia-exercise-set")
def run_generate_exercise_set(self, set_id: int, workspace_id: int, tool: str,
                              mode: str, count: int, source_uuid: str | None = None,
                              source_uuids: list[str] | None = None,
                              locale: str = "de"):
    """Generate items for an exercise set (flashcards/lueckentext/vokabeltest).

    `locale` controls the RAG sentinel string for source-cards generation
    (the AIA_SYSTEM_RAG prompt builder). Defaults to 'de' so older queued
    tasks keep working.
    """
    try:
        workspace = db.get_aia_workspace_by_id(workspace_id)
        if not workspace:
            db.fail_exercise_set(set_id)
            return

        client, model, _ = _get_llm_client()
        existing_fronts = db.get_existing_exercise_fronts(workspace_id, tool)

        items: list[dict] = []
        title = "Wird generiert…"

        if mode == "glossary":
            result = generate_from_glossary(client, model, workspace_id, tool, count)
            if result is None:
                db.fail_exercise_set(set_id)
                return
            items, title = result

        elif mode == "source":
            uuids = source_uuids or ([source_uuid] if source_uuid else [])
            if not uuids:
                db.fail_exercise_set(set_id)
                return
            ctx = build_source_context(uuids, tool)
            if ctx is None:
                db.fail_exercise_set(set_id)
                return

            if tool == "flashcards":
                items, title = generate_flashcards_from_source(client, model, ctx, count, existing_fronts)
            elif tool == "karteikarten":
                items, title = generate_cards_from_source(client, model, ctx, count, existing_fronts, locale=locale)
            else:
                items, title = generate_mc_from_source(client, model, ctx, tool, count, existing_fronts)

        if not items:
            db.fail_exercise_set(set_id)
            return

        db.finalize_exercise_set(set_id, title, items)
        logger.info("KI Tutor: exercise set {} generated ({} items)", set_id, len(items))

    except Exception as e:
        logger.error("KI Tutor: exercise set {} generation failed: {}", set_id, e)
        db.fail_exercise_set(set_id)


__all__ = ["run_generate_exercise_set"]
