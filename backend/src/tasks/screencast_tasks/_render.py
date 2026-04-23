"""Celery-Task: Final-MP4 aus bearbeiteten Scripts + gespeichertem PPTX rendern."""

from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.limits import SCREENCAST_SOFT_TIME_LIMIT, SCREENCAST_TIME_LIMIT
from src.storage import clear_tts_audio_cache, save_result_and_evict
from src.utils.heartbeat import job_heartbeat

from src.tasks.screencast_tasks._pipeline import _run_render_pipeline
from src.tasks.screencast_tasks._queue import _maybe_dispatch_next
from src.tasks.screencast_tasks._shared import _JobCancelled


@celery_app.task(
    bind=True,
    name="screencast.render",
    queue="screencast",
    acks_late=True,
    max_retries=7,
    soft_time_limit=SCREENCAST_SOFT_TIME_LIMIT,
    time_limit=SCREENCAST_TIME_LIMIT,
)
def run_screencast_render(
    self,
    translate_job_uuid: str,
    scripts: list[str],
    voice_id: str,
    speed: float,
    slide_pause: float,
    original_filename: str = "screencast",
    dpi: int = 100,
    provider: str = "elevenlabs",
    voice_label: str = "",
    is_admin: bool = False,
):
    """Render final MP4 from edited scripts and stored PPTX.

    Reads PPTX from the translate job's folder (corrected.pptx or translated.pptx).
    All artifacts are saved to the same folder (single-folder workflow).
    """
    from celery.exceptions import SoftTimeLimitExceeded
    try:
        db.update_job_status(translate_job_uuid, "running", progress={
            "step": "render", "voice_id": voice_id, "voice_label": voice_label, "provider": provider,
        })
        with job_heartbeat(translate_job_uuid):
            result = _run_render_pipeline(
                job_uuid=translate_job_uuid,
                scripts=scripts,
                voice_id=voice_id,
                speed=speed,
                slide_pause=slide_pause,
                dpi=dpi,
                provider=provider,
                is_admin=is_admin,
            )

        result_filename = f"{Path(original_filename).stem if original_filename else 'screencast'}.mp4"
        with job_heartbeat(translate_job_uuid):
            save_result_and_evict(translate_job_uuid, result["result_path"], result_filename)
        db.update_job_status(translate_job_uuid, "success")
        clear_tts_audio_cache(translate_job_uuid)

        logger.info("Screencast render task {} completed", translate_job_uuid)
        _maybe_dispatch_next(translate_job_uuid)

    except _JobCancelled:
        logger.info("Screencast render task {} cancelled by user", translate_job_uuid)
        db.reset_job_to_awaiting(translate_job_uuid)
        _maybe_dispatch_next(translate_job_uuid)  # awaiting_user hält keinen Slot → nächsten Job starten

    except SoftTimeLimitExceeded:
        logger.warning("Screencast render task {} hit soft time limit", translate_job_uuid)
        db.update_job_status(translate_job_uuid, "failed", error_message="Zeitlimit überschritten. Bitte 'Wiederholen' klicken.")
        _maybe_dispatch_next(translate_job_uuid)

    except Exception as e:
        logger.error("Screencast render task {} failed: {}", translate_job_uuid, e)
        db.update_job_status(translate_job_uuid, "failed", error_message=str(e))
        _maybe_dispatch_next(translate_job_uuid)
        raise
