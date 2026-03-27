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
        "src.tasks.ki_tutor_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=86400,  # 24h — matches file retention
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
        "ki_tutor.index_source": {"queue": "general"},
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
    """Mark a running job as failed based on its Celery task ID."""
    try:
        from src import database as db
        job = db.get_job_by_celery_task_id(task_id)
        if job:
            db.update_job_status(job["job_uuid"], "failed", error_message=reason)
            logger.warning("Signal: job {} marked failed — {}", job["job_uuid"][:8], reason)
    except Exception as e:
        logger.error("Signal handler error: {}", e)


@task_failure.connect
def on_task_failure(task_id, exception, **kwargs):
    from celery.exceptions import SoftTimeLimitExceeded
    if isinstance(exception, SoftTimeLimitExceeded):
        # Task body should have caught this and updated the DB already.
        # If it reaches here, the soft limit fired in an unguarded spot — still
        # give a friendly message rather than a raw exception string.
        _mark_task_failed(task_id, "Zeitlimit überschritten. Bitte 'Wiederholen' klicken.")
    else:
        _mark_task_failed(task_id, f"Unerwarteter Fehler: {exception}")


@task_revoked.connect
def on_task_revoked(request, terminated, signum, expired, **kwargs):
    if terminated or expired:
        _mark_task_failed(
            request.id,
            "Job hat sich nicht mehr gemeldet (möglicher Absturz oder Hänger). Bitte Wiederholen klicken.",
        )
