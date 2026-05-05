"""Heartbeat context manager for long-running external API calls.

Usage:
    from src.utils.heartbeat import job_heartbeat

    with job_heartbeat(job_uuid):
        result = some_slow_api_call(...)

The watchdog marks jobs as stuck if progress_updated_at is not updated for
JOB_WATCHDOG_MINUTES (see src/limits.py). This context manager fires a DB
heartbeat every 10 seconds during the wrapped call, keeping the timer fresh.
"""

import threading
from contextlib import contextmanager


@contextmanager
def job_heartbeat(job_uuid: str, interval: float = 30.0):
    """Send a DB heartbeat every `interval` seconds during a long operation."""
    from src import database as db

    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(interval):
            try:
                db.touch_job_heartbeat(job_uuid)
            except Exception:
                pass  # never crash the worker thread

    thread = threading.Thread(target=_beat, daemon=True, name=f"heartbeat-{job_uuid[:8]}")
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=interval + 2)
