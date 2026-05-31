"""User-Level Queue für Screencast-Jobs: dispatcht den nächsten wartenden Job."""

import json
import os

from loguru import logger

from src import database as db
from src.storage import get_job_file


_SCREENCAST_TOOLS = ["screencast_translate", "screencast_render"]


def dispatch_next_screencast_job_for_user(user_id: int) -> None:
    """Dispatch the oldest queued screencast job for this user, if any."""
    job = db.get_next_queued_job(user_id, _SCREENCAST_TOOLS)
    if not job:
        return
    job_uuid = job["job_uuid"]
    try:
        from src.tasks.screencast_tasks._translate import run_screencast_translate
        from src.tasks.screencast_tasks._render import run_screencast_render

        params = json.loads(get_job_file(user_id, job_uuid, "queue_params.json"))
        dispatch_as = params.get("dispatch_as", "")
        if dispatch_as == "translate":
            task = run_screencast_translate.apply_async(args=[
                job_uuid, params["input_path"], params["filename"],
                params["glossary_json"],
                params["source_lang"], params["target_lang"],
                params.get("provider_id"),
            ])
        elif dispatch_as == "render":
            scripts = json.loads(get_job_file(user_id, job_uuid, "render_scripts.json"))
            try:
                import redis as _redis
                _r = _redis.from_url(os.environ.get("REDIS_URL", "redis://kis-redis:6379/0"))
                _r.delete(f"job:cancel:{job_uuid}")
            except Exception:
                pass
            task = run_screencast_render.apply_async(args=[
                job_uuid, scripts,
                params["voice_id"], params["speed"], params["slide_pause"],
                job["original_filename"] or "screencast.pptx",
                params["dpi"], int(params.get("provider_id", 0)), params["voice_label"],
                params["is_admin"],
            ])
            db.set_render_queued_at(job_uuid)
        else:
            logger.warning("dispatch_next: unknown dispatch_as '{}' for job {}", dispatch_as, job_uuid[:8])
            db.update_job_status(job_uuid, "failed", error_message="Interner Fehler: Unbekannter Job-Typ in Warteschlange.")
            return
        db.set_job_celery_task_id(job_uuid, task.id)
        logger.info("dispatch_next: dispatched queued job {} ({})", job_uuid[:8], dispatch_as)
    except Exception as e:
        logger.error("dispatch_next: failed to dispatch job {}: {}", job_uuid[:8], e)
        db.update_job_status(job_uuid, "failed", error_message=f"Konnte nicht aus der Warteschlange gestartet werden: {e}")


def _maybe_dispatch_next(job_uuid: str) -> None:
    """After a job finishes, try to dispatch the next queued job for that user."""
    try:
        job = db.get_job(job_uuid)
        if job:
            dispatch_next_screencast_job_for_user(job["user_id"])
    except Exception as e:
        logger.warning("_maybe_dispatch_next failed for {}: {}", job_uuid[:8], e)
