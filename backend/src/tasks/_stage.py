"""A long job works in stages: work for a while, save, hand yourself back to the queue."""

from __future__ import annotations

import time

from loguru import logger

from src import database as db
from src.limits import CONTINUED_PRIORITY, STAGE_SECONDS


class StageContinue(Exception):
    """The stage did its share, the rest belongs to the next one."""


class StageLost(Exception):
    """Another run owns this job now, this one must write nothing more."""


class StageClock:
    """Counts the working time of one stage, asked before each new unit."""

    def __init__(self, seconds: float = STAGE_SECONDS) -> None:
        self._start = time.monotonic()
        self._seconds = seconds

    def spent(self) -> float:
        return time.monotonic() - self._start

    def over(self) -> bool:
        return self.spent() >= self._seconds


def continue_stage(task, args: list, job_uuid: str) -> None:
    """Queues the next stage of the same job, the row stays running throughout."""
    neu = task.apply_async(args=list(args), priority=CONTINUED_PRIORITY)
    db.set_job_celery_task_id(job_uuid, neu.id)
    logger.info("Auftrag {}: naechste Etappe eingereiht", job_uuid[:8])
