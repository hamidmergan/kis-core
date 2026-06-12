"""Production seam between AIA routes/tasks and the dispatch engine.

Default OFF: ``scheduler_enabled()`` reads ``aia_scheduler_enabled`` (default
"false"), so existing routes keep their direct ``.delay()`` behaviour until the
flag is flipped and the new path is verified in the live app. When on, routes
call ``enqueue_task`` and tasks call ``on_complete`` at the end.

Areas:
- ``ingest``  -> index_source, translate_transcript, reindex_*  (heavy lane)
- ``studio``  -> generate_* studio tools                         (interactive lane)

Caps are admin-tunable settings; the launch sends each task to its lane queue
``aia_ingest`` / ``aia_studio`` so the two worker pools stay hard-isolated.
"""
from __future__ import annotations

import time
import uuid as _uuid
from typing import Callable, Optional

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
    "aia.generate_glossary": "studio",
    "aia.generate_schedule": "studio",
}

_DEFAULT_CAPS = {"ingest": 2, "studio": 4}


def _default_get_setting(key: str, default: str = "") -> str:
    from src.features.admin.repository.settings import get_setting

    return get_setting(key, default)


def area_for_task(task_name: str) -> str:
    return AREA_FOR_TASK.get(task_name, "ingest")


def scheduler_enabled(get_setting: Callable[..., str] = _default_get_setting) -> bool:
    return str(get_setting("aia_scheduler_enabled", "false")).strip().lower() == "true"


def caps_from_settings(get_setting: Callable[..., str] = _default_get_setting) -> dict[str, int]:
    return {
        "ingest": int(get_setting("aia_ingest_concurrency", str(_DEFAULT_CAPS["ingest"]))),
        "studio": int(get_setting("aia_studio_concurrency", str(_DEFAULT_CAPS["studio"]))),
    }


def _launch(job: Job) -> str:
    """Send the real Celery task to its lane queue. Lazy import keeps this module
    importable without Celery/Redis (e.g. in unit tests)."""
    from src.celery_app import celery_app

    args = job.payload.get("args", [])
    kwargs = job.payload.get("kwargs", {})
    result = celery_app.send_task(
        job.task_name, args=args, kwargs=kwargs, queue=f"aia_{job.area}"
    )
    return result.id


def get_dispatch_service(
    store=None,
    launch: Optional[Callable[[Job], str]] = None,
    get_setting: Callable[..., str] = _default_get_setting,
) -> DispatchService:
    return DispatchService(
        store=store if store is not None else DbJobStore(),
        launch=launch if launch is not None else _launch,
        areas_config=caps_from_settings(get_setting),
    )


def enqueue_task(
    task_name: str,
    user_id: int,
    args: Optional[list] = None,
    kwargs: Optional[dict] = None,
    service: Optional[DispatchService] = None,
) -> str:
    """Enqueue a task into its lane and try to dispatch. Returns the aia_job uuid."""
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
    """Mark a job terminal and dispatch the next from the same lane."""
    svc = service if service is not None else get_dispatch_service()
    svc.on_complete(job_uuid, ok=ok, error=error)
