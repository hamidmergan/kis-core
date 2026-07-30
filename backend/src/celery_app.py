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
        "src.tasks.screencast_tasks",
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
        "general.summary": {"queue": "general"},
        "screencast.translate": {"queue": "screencast"},
        "screencast.render": {"queue": "screencast"},
        "watchdog.check": {"queue": "general"},
        "cleanup.expired_files": {"queue": "general"},
        "cleanup.prune_schedule": {"queue": "general"},
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
        # Lag vorher als Endlosschleife im Web-Prozess. Hier laeuft es garantiert
        # genau einmal, egal wie viele uvicorn-Prozesse es gibt.
        "cleanup-expired-files": {
            "task": "cleanup.expired_files",
            "schedule": 3600.0,  # stuendlich, wie vorher
            "options": {"queue": "general"},
        },
        "cleanup-prune-schedule": {
            "task": "cleanup.prune_schedule",
            "schedule": 86400.0,  # taeglich, wie vorher
            "options": {"queue": "general"},
        },
        # Naechtliche Datenbank-Sicherung in den Bucket. Feste Uhrzeit statt
        # Intervall, damit sie in der Nacht laeuft und nicht irgendwann am Tag,
        # abhaengig davon wann celery-beat zuletzt gestartet wurde.
        "backup-database": {
            "task": "backup.database",
            "schedule": crontab(hour=3, minute=30),
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
    """Mark a running job as failed based on its Celery task ID.

    `reason` is an i18n key (or a tuple `(key, params)`) so the persisted
    error_message can be localized using the job's `creator_locale`. Plain
    strings still work as a fallback for legacy callers.
    """
    try:
        from src import database as db
        from src.i18n import t
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
        db.update_job_status(job["job_uuid"], "failed", error_message=message)
        logger.warning("Signal: job {} marked failed - {}", job["job_uuid"][:8], message)
    except Exception as e:
        logger.error("Signal handler error: {}", e)


def _mark_aia_source_failed_from_signal(sender, args, exception) -> None:
    """Backstop for aia.index_source failures that escape the task body.

    The task already has an inner try/except that marks the source 'failed' for
    errors raised inside the function. Errors raised at the function boundary
    (e.g. signature mismatch when worker bytecode lags behind the codebase, or
    a SIGKILL'd worker) bypass that. Without this hook the source row stays at
    'queued'/'indexing' and the upload spinner never resolves.
    """
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
        # Task body should have caught this and updated the DB already.
        # If it reaches here, the soft limit fired in an unguarded spot - still
        # give a friendly message rather than a raw exception string.
        _mark_task_failed(task_id, "job.timeoutRetry")
    else:
        _mark_task_failed(task_id, ("job.unexpectedError", {"error": str(exception)}))


@task_revoked.connect
def on_task_revoked(request, terminated, signum, expired, **kwargs):
    if terminated or expired:
        _mark_task_failed(request.id, "job.watchdogStuck")
