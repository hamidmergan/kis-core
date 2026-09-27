"""One shared slot pool, split by area weight and then round robin per person."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from .scheduler import PoolJob, select_shared_pool


@dataclass
class Job:
    job_uuid: str
    user_id: int
    area: str
    task_name: str
    payload: dict
    created_at: float
    status: str = "queued"
    celery_task_id: Optional[str] = None
    error: Optional[str] = None


class JobStore(Protocol):
    def add(self, job: Job) -> None: ...
    def get(self, job_uuid: str) -> Optional[Job]: ...
    def queued_all(self) -> list[PoolJob]: ...
    def running_all(self) -> list[tuple[int, str]]: ...
    def area_grant_counts(self) -> dict[str, float]: ...
    def user_grant_counts(self) -> dict[int, int]: ...
    def mark_running(self, job_uuid: str) -> bool: ...
    def set_celery_task_id(self, job_uuid: str, celery_task_id: str) -> None: ...
    def mark_finished(self, job_uuid: str, ok: bool, error: Optional[str]) -> None: ...


class InMemoryJobStore:
    """Single-process store for tests and the stress run."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def add(self, job: Job) -> None:
        self._jobs[job.job_uuid] = job

    def get(self, job_uuid: str) -> Optional[Job]:
        return self._jobs.get(job_uuid)

    def queued_all(self) -> list[PoolJob]:
        return [
            PoolJob(j.job_uuid, j.user_id, j.area, j.created_at)
            for j in self._jobs.values()
            if j.status == "queued"
        ]

    def running_all(self) -> list[tuple[int, str]]:
        return [(j.user_id, j.area) for j in self._jobs.values() if j.status == "running"]

    def area_grant_counts(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for j in self._jobs.values():
            if j.status != "queued":
                out[j.area] = out.get(j.area, 0.0) + 1.0
        return out

    def user_grant_counts(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for j in self._jobs.values():
            if j.status != "queued":
                out[j.user_id] = out.get(j.user_id, 0) + 1
        return out

    def mark_running(self, job_uuid: str) -> bool:
        j = self._jobs.get(job_uuid)
        if j is None or j.status != "queued":
            return False
        j.status = "running"
        return True

    def set_celery_task_id(self, job_uuid: str, celery_task_id: str) -> None:
        j = self._jobs.get(job_uuid)
        if j is not None:
            j.celery_task_id = celery_task_id

    def mark_finished(self, job_uuid: str, ok: bool, error: Optional[str]) -> None:
        j = self._jobs.get(job_uuid)
        if j is None:
            return
        j.status = "done" if ok else "failed"
        j.error = error


class DispatchService:
    def __init__(
        self,
        store: JobStore,
        launch: Callable[[Job], str],
        total_slots: int,
        weights: dict[str, float],
        area_caps: Optional[dict[str, int]] = None,
    ) -> None:
        self.store = store
        self.launch = launch  # actually dispatch to Celery, return celery_task_id
        self.total_slots = total_slots
        self.weights = dict(weights)
        self.area_caps = dict(area_caps or {})

    def enqueue(self, job: Job) -> list[str]:
        self.store.add(job)
        return self.dispatch()

    def on_complete(self, job_uuid: str, ok: bool = True, error: Optional[str] = None) -> list[str]:
        self.store.mark_finished(job_uuid, ok, error)
        return self.dispatch()

    def dispatch(self) -> list[str]:
        """Starts every job the pool currently allows, slot claimed before the start."""
        # The areas share by what runs right now, a past burst of short jobs must not cost their area minutes.
        running = self.store.running_all()
        belegt: dict[str, float] = {}
        for _user_id, area in running:
            belegt[area] = belegt.get(area, 0.0) + 1.0
        picks = select_shared_pool(
            self.store.queued_all(), running, self.total_slots,
            self.weights, belegt, self.store.user_grant_counts(), self.area_caps,
        )
        started: list[str] = []
        for job_uuid in picks:
            job = self.store.get(job_uuid)
            if job is None:
                continue
            if not self.store.mark_running(job_uuid):
                continue  # lost the race to another dispatcher
            task_id = self.launch(job)
            self.store.set_celery_task_id(job_uuid, task_id)
            started.append(job_uuid)
        return started
