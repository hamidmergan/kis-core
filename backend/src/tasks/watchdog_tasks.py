"""Watchdog task: resumes due jobs, catches hanging ones, expires parked ones, frees orphaned slots."""

from datetime import datetime, timedelta, timezone

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.i18n import t
from src.limits import AWAITING_USER_TIMEOUT_HOURS, JOB_WATCHDOG_MINUTES
from src.services import broker_state, job_recovery


@celery_app.task(name="watchdog.check")
def check_stuck_jobs() -> None:
    # Each duty on its own, a broken one must not starve the other two.
    for pflicht in (_resume_due, _catch_stuck, _expire_parked, _reap_aia_slots):
        try:
            pflicht()
        except Exception as e:  # noqa: BLE001 - the next tick tries again in a few seconds
            logger.error("Watchdog: {} fehlgeschlagen: {}", pflicht.__name__, e)


def _resume_due() -> None:
    wieder = job_recovery.resume_due_jobs()
    if wieder:
        logger.info("Watchdog: {} Auftrag/Auftraege wieder angelaufen", wieder)


def _catch_stuck() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=JOB_WATCHDOG_MINUTES)
    stand = None
    stand_read = False
    for job in db.get_stuck_running_jobs(threshold_minutes=JOB_WATCHDOG_MINUTES):
        job_uuid = job["job_uuid"]
        if not stand_read:
            stand, stand_read = broker_state.snapshot(), True
        task_id = job.get("celery_task_id")
        # Waiting in line is no hang, also for the next stage of a running job.
        if stand is not None and task_id in stand.waiting:
            continue
        # A job not yet started is lost only once the broker no longer holds it at all.
        if job.get("status") == "pending" and (stand is None or stand.holds(task_id)):
            continue
        locale = job.get("creator_locale") or "de"
        logger.warning(
            "Watchdog: Auftrag {} ({}) meldet sich seit {} nicht mehr",
            job_uuid, job.get("tool", "?"), job.get("progress_updated_at", "?"),
        )
        # The job may have reported in between, then this leaves it alone.
        status = job_recovery.attempt_failed(
            job_uuid, t("job.watchdogStuck", locale), stale_before=cutoff)
        if not status:
            continue
        # Really end the run, otherwise the slot stays blocked until the time limit.
        if job.get("celery_task_id"):
            celery_app.control.revoke(job["celery_task_id"], terminate=True, signal="SIGTERM")


def _expire_parked() -> None:
    for job in db.get_stale_awaiting_user_jobs(threshold_hours=AWAITING_USER_TIMEOUT_HOURS):
        locale = job.get("creator_locale") or "de"
        logger.warning("Watchdog: Auftrag {} ({}) abgelaufen", job["job_uuid"], job.get("tool", "?"))
        db.expire_parked_job(job["job_uuid"], t("job.watchdogStaleAwaiting", locale))


def _reap_aia_slots() -> None:
    from src.features.ai_assistant.repository.jobs import DbJobStore
    from src.features.ai_assistant.scheduling import reaper, service

    reaper.reap(DbJobStore(), broker_state.snapshot(), reaper.outcome_of)
    # Fills free slots on every tick, not only when a job ends and reports.
    service.get_dispatch_service().dispatch()
