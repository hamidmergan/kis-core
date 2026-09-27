"""Connects routes and jobs to slot management, the slot count comes from the machine size."""
from __future__ import annotations

import json
import time
import uuid as _uuid
from typing import Callable, Optional

from src.limits import AIA_AREA_CAPS, AIA_AREA_WEIGHTS, AIA_PARALLEL_SLOTS
from src.features.ai_assistant.repository.jobs import DbJobStore
from src.features.ai_assistant.scheduling.dispatch_service import DispatchService, Job

AREA_FOR_TASK: dict[str, str] = {
    "aia.index_source": "ingest",
    "aia.translate_transcript": "ingest",
    "aia.reindex_all_sources": "ingest",
    "aia.reindex_workspace": "ingest",
    "aia.generate_mindmap": "studio",
    "aia.generate_exercise_set": "studio",
    "aia.generate_data_table": "studio",
    "aia.generate_schedule": "studio",
}


def _default_get_setting(key: str, default: str = "") -> str:
    from src.features.admin.repository.settings import get_setting

    return get_setting(key, default)


def area_for_task(task_name: str) -> str:
    return AREA_FOR_TASK.get(task_name, "ingest")


def scheduler_enabled(get_setting: Callable[..., str] = _default_get_setting) -> bool:
    """Always on, it only remains because the callers query it."""
    return True


def slots_from_settings(get_setting: Callable[..., str] = _default_get_setting) -> int:
    """Slots from the detected machine size, the signature stays for the tests."""
    return AIA_PARALLEL_SLOTS


def weights_from_settings(get_setting: Callable[..., str] = _default_get_setting) -> dict[str, float]:
    raw = get_setting("aia_area_weights", "")
    if raw:
        try:
            return {k: float(v) for k, v in json.loads(raw).items()}
        except Exception:
            pass
    return {k: float(v) for k, v in AIA_AREA_WEIGHTS.items()}


def _launch(job: Job) -> str:
    """Sends the Celery job into the queue its route names, with the job uuid."""
    from src.celery_app import celery_app

    args = job.payload.get("args", [])
    kwargs = dict(job.payload.get("kwargs", {}))
    kwargs["_aia_job_uuid"] = job.job_uuid
    queue = celery_app.conf.task_routes.get(job.task_name, {}).get("queue", "aia")
    result = celery_app.send_task(job.task_name, args=args, kwargs=kwargs, queue=queue)
    return result.id


def get_dispatch_service(
    store=None,
    launch: Optional[Callable[[Job], str]] = None,
    get_setting: Callable[..., str] = _default_get_setting,
) -> DispatchService:
    return DispatchService(
        store=store if store is not None else DbJobStore(),
        launch=launch if launch is not None else _launch,
        total_slots=slots_from_settings(get_setting),
        weights=weights_from_settings(get_setting),
        area_caps=AIA_AREA_CAPS,
    )


def enqueue_task(
    task_name: str,
    user_id: int,
    args: Optional[list] = None,
    kwargs: Optional[dict] = None,
    service: Optional[DispatchService] = None,
) -> str:
    """Enqueue a task into the shared pool and try to dispatch. Returns aia_job uuid."""
    job = Job(
        job_uuid=_uuid.uuid4().hex,
        user_id=user_id,
        area=area_for_task(task_name),
        task_name=task_name,
        payload={"args": list(args or []), "kwargs": dict(kwargs or {})},
        created_at=time.time(),
    )
    svc = service if service is not None else get_dispatch_service()
    svc.enqueue(job)
    return job.job_uuid


def on_complete(
    job_uuid: str,
    ok: bool = True,
    error: Optional[str] = None,
    service: Optional[DispatchService] = None,
) -> None:
    """Mark a job terminal and dispatch the next from the shared pool."""
    svc = service if service is not None else get_dispatch_service()
    svc.on_complete(job_uuid, ok=ok, error=error)
