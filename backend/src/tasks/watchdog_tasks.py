"""Watchdog task: periodically mark stuck running jobs as failed."""

from loguru import logger

from src.celery_app import celery_app
from src import database as db

# Jobs with no progress update for longer than this are considered stuck.
STUCK_THRESHOLD_MINUTES = 30 / 60  # 30 seconds — fallback for SIGKILL only

# awaiting_user jobs older than this are considered abandoned — cleaned up for storage.
AWAITING_USER_TIMEOUT_HOURS = 168  # 7 days — matches file retention, no slot blocked


@celery_app.task(name="watchdog.check")
def check_stuck_jobs() -> None:
    stuck = db.get_stuck_running_jobs(threshold_minutes=STUCK_THRESHOLD_MINUTES)
    if stuck:
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
                error_message="Job hat sich nicht mehr gemeldet (möglicher Absturz oder Hänger). Bitte Wiederholen klicken.",
            )
        logger.info("Watchdog: {} stuck job(s) marked as failed", len(stuck))

    stale = db.get_stale_awaiting_user_jobs(threshold_hours=AWAITING_USER_TIMEOUT_HOURS)
    if stale:
        for job in stale:
            job_uuid = job["job_uuid"]
            tool = job.get("tool", "?")
            logger.warning(
                "Watchdog: awaiting_user job {} ({}) timed out — marking as failed",
                job_uuid, tool,
            )
            db.update_job_status(
                job_uuid,
                "failed",
                error_message="Job abgelaufen (keine Eingabe erfolgt). Bitte neuen Screencast starten.",
            )
        logger.info("Watchdog: {} stale awaiting_user job(s) expired", len(stale))
