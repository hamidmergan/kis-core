"""Watchdog task: periodically mark stuck running jobs as failed."""

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.i18n import t

# Jobs with no progress update for longer than this are considered stuck.
STUCK_THRESHOLD_MINUTES = 5  # 5 minutes - the heartbeat fires every 10 s, so this is a generous safety net

# awaiting_user jobs older than this are considered abandoned - cleaned up for storage.
AWAITING_USER_TIMEOUT_HOURS = 168  # 7 days - matches file retention, no slot blocked


@celery_app.task(name="watchdog.check")
def check_stuck_jobs() -> None:
    stuck = db.get_stuck_running_jobs(threshold_minutes=STUCK_THRESHOLD_MINUTES)
    if stuck:
        for job in stuck:
            job_uuid = job["job_uuid"]
            last_update = job.get("progress_updated_at", "?")
            tool = job.get("tool", "?")
            celery_task_id = job.get("celery_task_id")
            logger.warning(
                "Watchdog: job {} ({}) stuck since {} - terminating and marking as failed",
                job_uuid, tool, last_update,
            )
            locale = job.get("creator_locale") or "de"
            db.update_job_status(
                job_uuid,
                "failed",
                error_message=t("job.watchdogStuck", locale),
            )
            # Revoke + terminate the Celery task so the worker slot is freed immediately.
            # Without this the slot stays blocked until the soft time limit fires (up to 60 min).
            if celery_task_id:
                celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")
                logger.info("Watchdog: revoked Celery task {} for job {}", celery_task_id, job_uuid[:8])
        logger.info("Watchdog: {} stuck job(s) marked as failed", len(stuck))

    stale = db.get_stale_awaiting_user_jobs(threshold_hours=AWAITING_USER_TIMEOUT_HOURS)
    if stale:
        for job in stale:
            job_uuid = job["job_uuid"]
            tool = job.get("tool", "?")
            logger.warning(
                "Watchdog: awaiting_user job {} ({}) timed out - marking as failed",
                job_uuid, tool,
            )
            locale = job.get("creator_locale") or "de"
            db.update_job_status(
                job_uuid,
                "failed",
                error_message=t("job.watchdogStaleAwaiting", locale),
            )
        logger.info("Watchdog: {} stale awaiting_user job(s) expired", len(stale))
