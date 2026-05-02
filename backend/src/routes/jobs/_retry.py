"""POST /jobs/{job_uuid}/retry - failed TTS/Screencast-Jobs wieder einreihen (ohne Doppelkosten)."""

import json

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.storage import get_job_file, save_job_file


router = APIRouter()


@router.post("/{job_uuid}/retry")
async def retry_job(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Re-queue a failed TTS job. Resumes from already-saved chunks - no double payment."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["tool"] not in ("tts", "screencast_translate", "screencast_render", "screencast_demo_render"):
        raise HTTPException(status_code=400, detail=t("job.retryOnlyTtsScreencast", locale))
    if job["status"] == "success":
        raise HTTPException(status_code=409, detail=t("job.alreadySuccessful", locale))
    if job["status"] in ("running", "pending"):
        raise HTTPException(status_code=409, detail=t("job.alreadyRunning", locale))
    progress = json.loads(job["progress"] or "{}")

    # Load and validate all params BEFORE claiming the job atomically
    if job["tool"] == "tts":
        if not job["input_path"]:
            raise HTTPException(status_code=400, detail=t("job.inputFileExpired", locale))
        params = progress.get("tts_params")
        if not params:
            raise HTTPException(status_code=400, detail=t("job.paramsNotSaved", locale))

    elif job["tool"] in ("screencast_translate", "screencast_render"):
        try:
            render_params = json.loads(get_job_file(job["user_id"], job_uuid, "render_params.json"))
            scripts = json.loads(get_job_file(job["user_id"], job_uuid, "render_scripts.json"))
        except Exception:
            raise HTTPException(status_code=400, detail=t("job.renderParamsExpired", locale))

    else:  # screencast_demo_render
        try:
            demo_params = json.loads(get_job_file(job["user_id"], job_uuid, "demo_params.json"))
        except Exception:
            raise HTTPException(status_code=400, detail=t("job.demoParamsExpired", locale))

    if job["tool"] == "tts":
        # Atomically claim the job - blocks parallel retries
        if not db.claim_job_for_retry(job_uuid):
            raise HTTPException(status_code=409, detail=t("job.parallelRunning", locale))

        from src.tasks.tts_tasks import run_tts
        task = run_tts.apply_async(args=[
            job_uuid,
            job["input_path"],
            job["original_filename"],
            params["voice_id"],
            params["speed"],
            params["stability"],
            params["similarity_boost"],
            params["style"],
            params["use_speaker_boost"],
            params["pause_preset"],
        ])
        try:
            import redis as _redis
            _r = _redis.from_url("redis://kis-redis:6379/0")
            _r.delete(f"job:cancel:{job_uuid}")
        except Exception as e:
            logger.warning("Could not clear cancel flag in Redis: {}", e)
        db.set_job_celery_task_id(job_uuid, task.id)

    elif job["tool"] in ("screencast_translate", "screencast_render"):
        save_job_file(job["user_id"], job_uuid, "queue_params.json", json.dumps({
            "dispatch_as": "render",
            "voice_id": render_params["voice_id"],
            "speed": render_params["speed"],
            "slide_pause": render_params["slide_pause"],
            "dpi": render_params["dpi"],
            "provider": render_params.get("provider", "elevenlabs"),
            "voice_label": render_params.get("voice_label", ""),
            "is_admin": render_params.get("is_admin", False),
        }).encode())
        if not db.transition_job_to_queued(job_uuid, job["user_id"], from_statuses=("failed",)):
            raise HTTPException(status_code=409, detail=t("job.parallelRunning", locale))
        from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
        dispatch_next_screencast_job_for_user(job["user_id"])

    else:  # screencast_demo_render
        save_job_file(job["user_id"], job_uuid, "queue_params.json", json.dumps({
            "dispatch_as": "demo_render",
            "dpi": demo_params["dpi"],
        }).encode())
        if not db.transition_job_to_queued(job_uuid, job["user_id"], from_statuses=("failed",)):
            raise HTTPException(status_code=409, detail=t("job.parallelRunning", locale))
        from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
        dispatch_next_screencast_job_for_user(job["user_id"])

    logger.info("{} job {} re-queued via retry by user {}", job["tool"], job_uuid, current_user.get("user_id"))
    return {"ok": True}
