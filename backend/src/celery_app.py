from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure, task_revoked, worker_ready
from loguru import logger

celery_app = Celery(
    "kis",
    broker="redis://kis-redis:6379/0",
    backend="redis://kis-redis:6379/1",
    include=[
        "src.tasks.tts_tasks",
        "src.tasks.general_tasks",
        "src.tasks.summary_tasks",
        "src.tasks.screencast_tasks",
        "src.tasks.podcast_tasks",
        "src.tasks.watchdog_tasks",
        "src.tasks.cleanup_tasks",
        "src.tasks.backup_tasks",
        "src.tasks.aia_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=86400,  # 24h - matches file retention
    worker_max_tasks_per_child=10,  # restart worker every 10 tasks (prevent memory leaks)
    task_acks_late=True,  # only ack after task completes (no lost jobs on worker crash)
    worker_prefetch_multiplier=1,  # one task at a time per worker process
    task_routes={
        "tts.run": {"queue": "tts"},
        "general.translate": {"queue": "general"},
        "general.transcribe": {"queue": "general"},
        "general.image_generate": {"queue": "general"},
        "general.image_edit": {"queue": "general"},
        "general.image_analyze": {"queue": "general"},
        "summary.run": {"queue": "general"},
        "screencast.translate": {"queue": "screencast"},
        "screencast.render": {"queue": "screencast"},
        # Podcast waits on the voice provider, it does not compute: the general worker scales.
        "podcast.script": {"queue": "general"},
        "podcast.render": {"queue": "general"},
        "watchdog.check": {"queue": "general"},
        "cleanup.expired_files": {"queue": "general"},
        "cleanup.job_cap": {"queue": "general"},
        "cleanup.exercise_progress": {"queue": "general"},
        "backup.database": {"queue": "general"},
        # AI tutor: dedicated queue for learning tools and language training
        "aia.index_source": {"queue": "aia"},
        "aia.generate_mindmap": {"queue": "aia"},
        "aia.generate_exercise_set": {"queue": "aia"},
        "aia.generate_data_table": {"queue": "aia"},
        "aia.generate_glossary": {"queue": "aia"},
    },
    beat_schedule={
        "watchdog-stuck-jobs": {
            "task": "watchdog.check",
            "schedule": 5.0,  # every 5 seconds
            "options": {"queue": "general"},
        },
        # Runs exactly once here, no matter how many uvicorn processes exist.
        "cleanup-expired-files": {
            "task": "cleanup.expired_files",
            "schedule": 3600.0,  # stuendlich, wie vorher
            "options": {"queue": "general"},
        },
        # The job pool is the only retention rule.
        "cleanup-job-cap": {
            "task": "cleanup.job_cap",
            "schedule": 3600.0,  # stuendlich
            "options": {"queue": "general"},
        },
        # Locks accounts whose access-code deadline passed, never deletes them.
        "cleanup-lock-expired-access-accounts": {
            "task": "cleanup.lock_expired_access_accounts",
            "schedule": 3600.0,  # stuendlich
            "options": {"queue": "general"},
        },
        # A fixed time instead of an interval, so the backup runs at night.
        "backup-database": {
            "task": "backup.database",
            "schedule": crontab(hour=3, minute=30),
            "options": {"queue": "general"},
        },
        # After the backup, so what was deleted had been backed up.
        "cleanup-exercise-progress": {
            "task": "cleanup.exercise_progress",
            "schedule": crontab(hour=4, minute=15),
            "options": {"queue": "general"},
        },
        # Removes test accounts locked longer than the grace period, after the backup.
        "cleanup-delete-expired-access-accounts": {
            "task": "cleanup.delete_expired_access_accounts",
            "schedule": crontab(hour=4, minute=45),
            "options": {"queue": "general"},
        },
        # Spoken example sentences nobody has listened to for a long time.
        "cleanup-speech-cache": {
            "task": "cleanup.speech_cache",
            "schedule": crontab(hour=4, minute=30),
            "options": {"queue": "general"},
        },
    },
)


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Clean up stale /tmp dirs left behind by SIGKILL'd tasks from a previous run."""
    import shutil
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.gettempdir())
    cleaned = 0
    for d in tmp.glob("tmp*"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            cleaned += 1
    if cleaned:
        logger.info("Worker startup: removed {} stale temp dirs from {}", cleaned, tmp)


def _mark_task_failed(task_id: str, reason: str) -> None:
    """Counts one failed attempt for a running job, found via its Celery id."""
    try:
        from src import database as db
        from src.i18n import t
        from src.services import job_recovery
        job = db.get_job_by_celery_task_id(task_id)
        if not job:
            return
        locale = job.get("creator_locale") or "de"
        if isinstance(reason, tuple):
            key, params = reason
            message = t(key, locale, **params)
        elif isinstance(reason, str) and "." in reason and " " not in reason:
            message = t(reason, locale)
        else:
            message = reason
        status = job_recovery.attempt_failed(job["job_uuid"], message)
        logger.warning("Signal: job {} now {} - {}", job["job_uuid"][:8], status, message)
    except Exception as e:
        logger.error("Signal handler error: {}", e)


def _mark_aia_source_failed_from_signal(sender, args, exception) -> None:
    """Catches errors that arise at the function edge of aia.index_source."""
    if sender is None or sender.name != "aia.index_source":
        return
    if not args or not isinstance(args[0], str):
        return
    source_uuid = args[0]
    locale = args[1] if len(args) > 1 and isinstance(args[1], str) else "de"
    try:
        from src import database as db
        from src.i18n import t
        source = db.get_aia_source(source_uuid)
        if not source or source.get("status") == "failed":
            return
        message = t("job.unexpectedError", locale, error=str(exception))
        db.update_aia_source_status(source_uuid, "failed", error_message=message)
        logger.warning("Signal: aia_source {} marked failed - {}", source_uuid[:8], message)
    except Exception as e:
        logger.error("Signal handler (aia_source) error: {}", e)


@task_failure.connect
def on_task_failure(task_id, exception, **kwargs):
    _mark_aia_source_failed_from_signal(kwargs.get("sender"), kwargs.get("args") or (), exception)

    from celery.exceptions import SoftTimeLimitExceeded
    if isinstance(exception, SoftTimeLimitExceeded):
        # A friendly message instead of a raw exception if the deadline struck unguarded.
        _mark_task_failed(task_id, "job.timeoutRetry")
    else:
        _mark_task_failed(task_id, ("job.unexpectedError", {"error": str(exception)}))


@task_revoked.connect
def on_task_revoked(request, terminated, signum, expired, **kwargs):
    if terminated or expired:
        _mark_task_failed(request.id, "job.watchdogStuck")
