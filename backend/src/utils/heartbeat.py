"""A heartbeat for phases without units, where no finished piece can report instead.

A loop over units must call ``db.touch_job_heartbeat`` per finished unit rather than
use this, otherwise a job that hangs keeps breathing and the watchdog never sees it.
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
