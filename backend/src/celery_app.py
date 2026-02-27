from celery import Celery

celery_app = Celery(
    "kis",
    broker="redis://kis-redis:6379/0",
    backend="redis://kis-redis:6379/1",
    include=[
        "src.tasks.tts_tasks",
        "src.tasks.general_tasks",
        "src.tasks.screencast_tasks",
        "src.tasks.video_dubbing_tasks",
        "src.tasks.watchdog_tasks",
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
        "video_dubbing.submit": {"queue": "dubbing"},
        "video_dubbing.download": {"queue": "dubbing"},
        "video_dubbing.poll": {"queue": "dubbing"},
        "watchdog.check": {"queue": "screencast"},
    },
    beat_schedule={
        "poll-dubbing-jobs": {
            "task": "video_dubbing.poll",
            "schedule": 15.0,  # every 15 seconds
        },
        "watchdog-stuck-jobs": {
            "task": "watchdog.check",
            "schedule": 60.0,  # every 1 minute
            "options": {"queue": "screencast"},
        },
    },
)
