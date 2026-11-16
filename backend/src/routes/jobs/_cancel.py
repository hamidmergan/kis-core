"""Soft cancel and hard delete of a job."""

import shutil

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.core.redis_url import REDIS_URL
from src.celery_app import celery_app
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.storage import delete_job_folder

from src.routes.jobs._shared import _SCREENCAST_TOOLS, set_cancel_flag


router = APIRouter()


def stop_worker(job: dict) -> None:
    """Stops the worker of a job, by revoking its task and by the cancel flag."""
    # terminate=True sends SIGTERM to the worker process.
    if job["celery_task_id"]:
        try:
            celery_app.control.revoke(job["celery_task_id"], terminate=True, reply=False)
        except Exception as e:
            logger.warning("Could not revoke Celery task {}: {}", job["celery_task_id"], e)
    # Without the flag the worker keeps running until its task ends.
    set_cancel_flag(job["job_uuid"])


def remove_job(job: dict) -> None:
    """Stops a job and removes its files, its row and its traces, then lets the owner's next one run."""
    job_uuid = job["job_uuid"]
    stop_worker(job)

    # Delete all job files first, then the DB row.
    delete_job_folder(job["user_id"], job_uuid)
    db.delete_job(job_uuid)

    # Notify the interface about the changed list.
    try:
        import redis as _redis_notify
        _rn = _redis_notify.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        _rn.publish(f"jobs:{job['user_id']}", "update")
        _rn.close()
    except Exception as e:
        logger.warning("Could not notify SSE after job delete: {}", e)

    # Clean up pre-rendered slide image cache (screencast jobs only, ignored for others)
    try:
        from src.services.screencast import IMAGE_TMP_DIR
        shutil.rmtree(IMAGE_TMP_DIR / job_uuid, ignore_errors=True)
    except Exception:
        pass

    # If a screencast job was cancelled, dispatch the next queued job for this user
    if job.get("tool") in _SCREENCAST_TOOLS:
        try:
            from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
            dispatch_next_screencast_job_for_user(job["user_id"])
        except Exception as e:
            logger.warning("Could not dispatch next queued screencast job after cancel: {}", e)


def _own_job(job_uuid: str, current_user: dict, locale: str) -> dict:
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail=t("job.accessDenied", locale))
    return job


@router.post("/{job_uuid}/cancel")
def cancel_job_render(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Stop a running render without deleting job data. Sets status back to awaiting_user."""
    job = _own_job(job_uuid, current_user, locale)
    stop_worker(job)

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
    remove_job(_own_job(job_uuid, current_user, locale))
    logger.info("Job cancelled: {}", job_uuid)
    return {"ok": True}
