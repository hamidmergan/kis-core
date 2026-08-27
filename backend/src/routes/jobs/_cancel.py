"""Soft cancel and hard delete of a job."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.storage import delete_job_folder

from src.routes.jobs._shared import _SCREENCAST_TOOLS


router = APIRouter()


@router.post("/{job_uuid}/cancel")
def cancel_job_render(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Stop a running render without deleting job data. Sets status back to awaiting_user."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail=t("job.accessDenied", locale))

    if job["celery_task_id"]:
        try:
            celery_app.control.revoke(job["celery_task_id"], terminate=True, reply=False)
        except Exception as e:
            logger.warning("Could not revoke Celery task {}: {}", job["celery_task_id"], e)

    # Set a Redis cancellation flag so the worker stops at the next checkpoint
    try:
        import redis as _redis
        _r = _redis.from_url("redis://kis-redis:6379/0")
        _r.setex(f"job:cancel:{job_uuid}", 600, "1")  # 10 min TTL
        logger.info("Cancel flag set in Redis for job={}", job_uuid)
    except Exception as e:
        logger.warning("Could not set cancel flag in Redis: {}", e)

    db.reset_job_to_awaiting(job_uuid)
    try:
        from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
        dispatch_next_screencast_job_for_user(job["user_id"])
    except Exception as e:
        logger.warning("Could not dispatch next queued job after soft-cancel: {}", e)
    logger.info("Job render soft-cancelled: {}", job_uuid)
    return {"ok": True}


@router.delete("/{job_uuid}")
def cancel_job(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Cancel and delete a job. Revokes the Celery task if still running."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail=t("job.accessDenied", locale))

    # Revoke the Celery task (terminate=True sends SIGTERM to the worker process)
    if job["celery_task_id"]:
        try:
            celery_app.control.revoke(job["celery_task_id"], terminate=True, reply=False)
        except Exception as e:
            logger.warning("Could not revoke Celery task {}: {}", job["celery_task_id"], e)

    # The cancel marker in Redis, otherwise the worker keeps running.
    try:
        import redis as _redis
        _r = _redis.from_url("redis://kis-redis:6379/0")
        _r.setex(f"job:cancel:{job_uuid}", 600, "1")
    except Exception as e:
        logger.warning("Could not set cancel flag in Redis: {}", e)

    # Delete all job files first, then the DB row.
    delete_job_folder(job["user_id"], job_uuid)
    db.delete_job(job_uuid)

    # Notify the interface about the changed list.
    try:
        import redis as _redis_notify
        _rn = _redis_notify.from_url("redis://kis-redis:6379/0", socket_connect_timeout=1, socket_timeout=1)
        _rn.publish(f"jobs:{job['user_id']}", "update")
        _rn.close()
    except Exception as e:
        logger.warning("Could not notify SSE after job delete: {}", e)

    # Clean up pre-rendered slide image cache (screencast jobs only, ignored for others)
    try:
        import shutil as _shutil
        from src.services.screencast import IMAGE_TMP_DIR
        _shutil.rmtree(IMAGE_TMP_DIR / job_uuid, ignore_errors=True)
    except Exception:
        pass

    # If a screencast job was cancelled, dispatch the next queued job for this user
    if job.get("tool") in _SCREENCAST_TOOLS:
        try:
            from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
            dispatch_next_screencast_job_for_user(job["user_id"])
        except Exception as e:
            logger.warning("Could not dispatch next queued screencast job after cancel: {}", e)

    logger.info("Job cancelled: {}", job_uuid)
    return {"ok": True}
