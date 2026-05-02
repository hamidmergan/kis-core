from celery import Celery
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
        "general.script": {"queue": "general"},
        "general.summary": {"queue": "general"},
        "screencast.translate": {"queue": "screencast"},
        "screencast.render": {"queue": "screencast"},
        "screencast.auto": {"queue": "screencast"},
        "screencast.demo_render": {"queue": "screencast"},
        "watchdog.check": {"queue": "general"},
        # AI tutor: dedicated queue for learning tools and language training
        "kia.index_source": {"queue": "kia"},
        "kia.generate_summaries": {"queue": "kia"},
        "kia.generate_mindmap": {"queue": "kia"},
        "kia.generate_exercise_set": {"queue": "kia"},
        "kia.generate_data_table": {"queue": "kia"},
        "kia.generate_glossary": {"queue": "kia"},
    },
    beat_schedule={
        "watchdog-stuck-jobs": {
            "task": "watchdog.check",
            "schedule": 5.0,  # every 5 seconds
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


@task_failure.connect
def on_task_failure(task_id, exception, **kwargs):
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
