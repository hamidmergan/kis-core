"""Loads the screencast tasks so Celery knows them."""

from src.tasks.screencast_tasks._queue import (
    dispatch_next_screencast_job_for_user,
)
from src.tasks.screencast_tasks._render import run_screencast_render
from src.tasks.screencast_tasks._translate import run_screencast_translate


__all__ = [
    "run_screencast_render",
    "run_screencast_translate",
    "dispatch_next_screencast_job_for_user",
]
