"""Watchdog task: periodically mark stuck running jobs as failed."""

from loguru import logger

from src.celery_app import celery_app
from src import database as db

# Jobs with no progress update for longer than this are considered stuck.
STUCK_THRESHOLD_MINUTES = 20


@celery_app.task(name="watchdog.check")
def check_stuck_jobs() -> None:
    stuck = db.get_stuck_running_jobs(threshold_minutes=STUCK_THRESHOLD_MINUTES)
    if not stuck:
        return
    for job in stuck:
        job_uuid = job["job_uuid"]
        last_update = job.get("progress_updated_at", "?")
        tool = job.get("tool", "?")
        logger.warning(
            "Watchdog: job {} ({}) stuck since {} — marking as failed",
            job_uuid, tool, last_update,
        )
        db.update_job_status(
            job_uuid,
            "failed",
            error_message=f"Job hat sich seit über {STUCK_THRESHOLD_MINUTES} Minuten nicht mehr gemeldet (möglicher Absturz oder Hänger).",
        )
    logger.info("Watchdog: {} stuck job(s) marked as failed", len(stuck))
