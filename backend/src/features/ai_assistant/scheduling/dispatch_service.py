"""Dispatch orchestration: enqueue, decide what runs, re-dispatch on completion.

This is the heart that the routes and tasks talk to. It is storage-agnostic via
the ``JobStore`` protocol, so the orchestration logic is unit-tested in memory
and runs against the ``aia_jobs`` DB table in production.

Flow:
- ``enqueue(job)``   -> persist as 'queued', then try to start whatever capacity
                        and per-user fairness allow.
- ``on_complete()``  -> mark terminal, then re-dispatch to fill the freed slot.

Concurrency caps come from ``areas_config`` ({area: cap}) and are the hard
per-lane bottleneck. Lanes never share slots.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from .fair_dispatch import QueuedJob, select_next_dispatches


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
    def queued(self, area: str) -> list[QueuedJob]: ...
    def running_user_ids(self, area: str) -> list[int]: ...
    def mark_running(self, job_uuid: str, celery_task_id: str) -> None: ...
    def mark_finished(self, job_uuid: str, ok: bool, error: Optional[str]) -> None: ...


class InMemoryJobStore:
    """Single-process store for tests and the stress run."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def add(self, job: Job) -> None:
        self._jobs[job.job_uuid] = job

    def get(self, job_uuid: str) -> Optional[Job]:
        return self._jobs.get(job_uuid)

    def queued(self, area: str) -> list[QueuedJob]:
        return [
            QueuedJob(j.job_uuid, j.user_id, j.created_at)
            for j in self._jobs.values()
            if j.area == area and j.status == "queued"
        ]

    def running_user_ids(self, area: str) -> list[int]:
        return [
            j.user_id
            for j in self._jobs.values()
            if j.area == area and j.status == "running"
        ]

    def mark_running(self, job_uuid: str, celery_task_id: str) -> None:
        j = self._jobs[job_uuid]
        j.status = "running"
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
        areas_config: dict[str, int],
    ) -> None:
        self.store = store
        self.launch = launch  # actually dispatch to Celery, return celery_task_id
        self.areas_config = dict(areas_config)

    def enqueue(self, job: Job) -> list[str]:
        self.store.add(job)
        return self.dispatch()

    def on_complete(self, job_uuid: str, ok: bool = True, error: Optional[str] = None) -> list[str]:
        self.store.mark_finished(job_uuid, ok, error)
        return self.dispatch()

    def dispatch(self) -> list[str]:
        """Start every job that capacity and fairness currently allow."""
        started: list[str] = []
        for area, cap in self.areas_config.items():
            picks = select_next_dispatches(
                self.store.queued(area), self.store.running_user_ids(area), cap
            )
            for job_uuid in picks:
                job = self.store.get(job_uuid)
                if job is None:
                    continue
                task_id = self.launch(job)
                self.store.mark_running(job_uuid, task_id)
                started.append(job_uuid)
        return started
