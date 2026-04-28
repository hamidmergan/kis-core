"""KI-Assistent Celery-Task: Exercise-Set-Generierung.

Dispatcht je nach `mode` (glossar/quelle) und `tool`
(lernkarten/karteikarten/lueckentext/quiz/vokabeltest) an die passenden
Handler-Module."""

from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.ki_assistent.tasks._helpers import _get_llm_client

from src.features.ki_assistent.tasks.sprachtraining._context import build_quelle_context
from src.features.ki_assistent.tasks.sprachtraining._glossar import generate_from_glossary
from src.features.ki_assistent.tasks.sprachtraining._quelle_karteikarten import (
    generate_karteikarten_from_source,
)
from src.features.ki_assistent.tasks.sprachtraining._quelle_lernkarten import (
    generate_lernkarten_from_source,
)
from src.features.ki_assistent.tasks.sprachtraining._quelle_mc import generate_mc_from_source


@celery_app.task(bind=True, name="kia.generate_exercise_set", queue="kia",
                 soft_time_limit=120, time_limit=180)
@observe(name="kia-exercise-set")
def run_generate_exercise_set(self, set_id: int, module_id: int, tool: str,
                              mode: str, count: int, source_uuid: str | None = None,
                              source_uuids: list[str] | None = None):
    """Generate items for an exercise set (lernkarten/lueckentext/vokabeltest)."""
    try:
        module = db.get_kia_module_by_id(module_id)
        if not module:
            db.fail_exercise_set(set_id)
            return

        client, model, _ = _get_llm_client()
        existing_fronts = db.get_existing_exercise_fronts(module_id, tool)

        items: list[dict] = []
        title = "Wird generiert…"

        if mode == "glossar":
            result = generate_from_glossary(client, model, module_id, tool, count)
            if result is None:
                db.fail_exercise_set(set_id)
                return
            items, title = result

        elif mode == "quelle":
            uuids = source_uuids or ([source_uuid] if source_uuid else [])
            if not uuids:
                db.fail_exercise_set(set_id)
                return
            ctx = build_quelle_context(uuids, tool)
            if ctx is None:
                db.fail_exercise_set(set_id)
                return

            if tool == "lernkarten":
                items, title = generate_lernkarten_from_source(client, model, ctx, count, existing_fronts)
            elif tool == "karteikarten":
                items, title = generate_karteikarten_from_source(client, model, ctx, count, existing_fronts)
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
