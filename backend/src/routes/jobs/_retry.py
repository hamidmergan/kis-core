"""Re-queues failed or paused jobs without charging twice."""

import json

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.storage import get_job_file, save_job_file


router = APIRouter()


def _queue_params_from_render(render_params: dict) -> dict:
    """The stored render details as a job for the queue."""
    return {
        "dispatch_as": "render",
        "voice_id": render_params["voice_id"],
        "speed": render_params["speed"],
        "slide_pause": render_params["slide_pause"],
        "dpi": render_params["dpi"],
        "provider_id": int(render_params.get("provider_id", 0)),
        "voice_label": render_params.get("voice_label", ""),
        "is_admin": render_params.get("is_admin", False),
        "subtitles": bool(render_params.get("subtitles", False)),
        "video_folien": render_params.get("video_folien"),
        "neu_vertonen": render_params.get("neu_vertonen") or [],
    }


@router.post("/{job_uuid}/retry")
def retry_job(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Re-queue a failed TTS job. Resumes from already-saved chunks - no double payment."""
    job = db.get_job(job_uuid)
    # Owner-only: without this any user could re-queue another user's failed job.
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["tool"] not in ("tts", "screencast_translate", "screencast_render", "summary"):
        raise HTTPException(status_code=400, detail=t("job.retryOnlyTtsScreencast", locale))
    if job["status"] == "success":
        raise HTTPException(status_code=409, detail=t("job.alreadySuccessful", locale))
    if job["status"] not in ("failed", "paused"):
        raise HTTPException(status_code=409, detail=t("job.alreadyRunning", locale))
    progress = json.loads(job["progress"] or "{}")

    # Load and validate all params BEFORE claiming the job atomically
    if job["tool"] == "tts":
        if not job["input_path"]:
            raise HTTPException(status_code=400, detail=t("job.inputFileExpired", locale))
        # The folder is the reliable source, the progress gets overwritten while running.
        try:
            params = json.loads(get_job_file(job["user_id"], job_uuid, "tts_params.json"))
        except Exception:
            params = progress.get("tts_params")
        if not params:
            raise HTTPException(status_code=400, detail=t("job.paramsNotSaved", locale))

    elif job["tool"] == "summary":
        try:
            get_job_file(job["user_id"], job_uuid, "summary_params.json")
        except Exception:
            raise HTTPException(status_code=400, detail=t("job.paramsNotSaved", locale))

    else:  # screencast_translate / screencast_render
        render_params = None
        try:
            render_params = json.loads(get_job_file(job["user_id"], job_uuid, "render_params.json"))
            json.loads(get_job_file(job["user_id"], job_uuid, "render_scripts.json"))
        except Exception:
            # Paused before the voicing: the translation's own queue details carry it on.
            try:
                get_job_file(job["user_id"], job_uuid, "queue_params.json")
            except Exception:
                raise HTTPException(status_code=400, detail=t("job.renderParamsExpired", locale))

    if job["tool"] == "tts":
        # Atomically claim the job - blocks parallel retries
        if not db.claim_job_for_retry(job_uuid):
            raise HTTPException(status_code=409, detail=t("job.parallelRunning", locale))

        from src.tasks.tts_tasks import run_tts
        provider_id = int(params.get("provider_id", 0))
        task = run_tts.apply_async(args=[
            job_uuid,
            job["input_path"],
            job["original_filename"],
            params["voice_id"],
            params["speed"],
            provider_id,
            params.get("voice_label", ""),
            0,
        ])
        try:
            import redis as _redis
            _r = _redis.from_url("redis://kis-redis:6379/0")
            _r.delete(f"job:cancel:{job_uuid}")
        except Exception as e:
            logger.warning("Could not clear cancel flag in Redis: {}", e)
        db.set_job_celery_task_id(job_uuid, task.id)

    elif job["tool"] == "summary":
        if not db.claim_job_for_retry(job_uuid):
            raise HTTPException(status_code=409, detail=t("job.parallelRunning", locale))
        from src.services import job_recovery
        job_recovery.dispatch_resume({**job, "attempts": 0})

    else:  # screencast_translate / screencast_render
        if render_params is not None:
            save_job_file(job["user_id"], job_uuid, "queue_params.json",
                          json.dumps(_queue_params_from_render(render_params)).encode())
        if not db.transition_job_to_queued(job_uuid, job["user_id"],
                                           from_statuses=("failed", "paused")):
            raise HTTPException(status_code=409, detail=t("job.parallelRunning", locale))
        db.reset_attempts(job_uuid)
        from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
        dispatch_next_screencast_job_for_user(job["user_id"])

    logger.info("{} job {} re-queued via retry by user {}", job["tool"], job_uuid, current_user.get("user_id"))
    return {"ok": True}
