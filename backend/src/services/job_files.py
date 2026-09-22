"""Text files of a job folder, and the progress row a long run keeps writing."""

import json
from typing import Callable

from loguru import logger

from src import database as db
from src.storage import get_job_file, job_file_exists, save_job_file


def read_job_text(user_id: int, job_uuid: str, name: str) -> str | None:
    """A text file of the job folder, None when it is missing or unreadable."""
    if not job_file_exists(user_id, job_uuid, name):
        return None
    try:
        return get_job_file(user_id, job_uuid, name).decode("utf-8")
    except Exception as e:  # noqa: BLE001 - an unreadable piece is simply redone
        logger.warning("Auftrag {}: {} nicht lesbar ({})", job_uuid[:8], name, e)
        return None


def write_job_text(user_id: int, job_uuid: str, name: str, text: str) -> None:
    """One text file into the job folder, the counterpart of read_job_text."""
    save_job_file(user_id, job_uuid, name, text.encode("utf-8"))


def parse_job_json(job_uuid: str, name: str, raw: str | None, default):
    """Same fallback as an unreadable file: a broken one is treated as absent."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Auftrag {}: {} beschaedigt ({})", job_uuid[:8], name, e)
        return default


class JobState:
    """The job folder as a long run sees it, with the guard every write passes.

    The guard is handed in rather than looked up, so this knows nothing about stages.
    """

    def __init__(self, user_id: int, job_uuid: str,
                 guard: Callable[[], None] | None = None) -> None:
        self._user = user_id
        self._job = job_uuid
        self._guard_hook = guard

    def _guard(self) -> None:
        """Asked before every write, so a run that lost its claim stops writing."""
        if self._guard_hook is not None:
            self._guard_hook()

    def heartbeat(self) -> None:
        self._guard()
        db.touch_job_heartbeat(self._job)

    def progress(self, step: str, part: int | None = None,
                 total: int | None = None) -> None:
        self._guard()
        fortschritt: dict = {"step": step}
        if part is not None and total is not None:
            fortschritt |= {"part": part, "total": total}
        db.update_job_status(self._job, "running", progress=fortschritt)
        db.touch_job_heartbeat(self._job)
