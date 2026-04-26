"""KI-Assistent routes — schedule."""

from datetime import date, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_current_user
from src.features.ki_assistent import schemas

router = APIRouter(tags=["ki-assistent"])


# ─── Helpers ────────────────────────────────────────────────────────────────

def _require_module_access(module_uuid: str, user_id: int) -> dict:
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    return module


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Ungültiges Datum: {s}")


def _parse_time(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    try:
        parts = s.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail=f"Ungültige Uhrzeit: {s}")


def _serialize_entry(row: dict) -> dict:
    """DB-row → JSON-safe dict for API response."""
    return {
        "id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "description": row.get("description"),
        "due_date": row["due_date"].isoformat() if row.get("due_date") else None,
        "due_time": row["due_time"].strftime("%H:%M") if row.get("due_time") else None,
        "is_optional": row["is_optional"],
        "is_checked": row["is_checked"],
        "checked_at": row["checked_at"].isoformat() + "Z" if row.get("checked_at") else None,
        "origin": row["origin"],
        "source_refs": row.get("source_refs") or [],
        "created_at": row["created_at"].isoformat() + "Z" if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() + "Z" if row.get("updated_at") else None,
    }


# ─── GLOBAL SCHEDULE (across all owned + enrolled modules) ─────────────────

def _serialize_global_entry(row: dict) -> dict:
    """Serialize a row enriched with module info (owned vs. enrolled)."""
    return {
        "id": row["id"],
        "module_uuid": row["module_uuid"],
        "module_title": row["module_title"],
        "module_relation": row["module_relation"],
        "type": row["type"],
        "title": row["title"],
        "description": row.get("description"),
        "due_date": row["due_date"].isoformat() if row.get("due_date") else None,
        "due_time": row["due_time"].strftime("%H:%M") if row.get("due_time") else None,
        "is_checked": row["is_checked"],
    }


@router.get("/ki-assistent/schedule/upcoming")
async def get_upcoming_schedule(
    limit: Optional[int] = None,
    offset: int = 0,
    include_checked: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Top-N upcoming schedule entries across all the user's modules
    (owned + enrolled). Used by the home widget (limit=5) and the global
    overview page (paginated with limit + offset).
    """
    if limit is not None and (limit < 1 or limit > 500):
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    user_id = current_user["user_id"]
    rows = db.get_schedule_entries_for_user(
        user_id, limit=limit, offset=offset, include_checked=include_checked,
    )
    return {"entries": [_serialize_global_entry(r) for r in rows]}


# ─── GET ────────────────────────────────────────────────────────────────────

@router.get("/ki-assistent/modules/{module_uuid}/schedule")
async def get_schedule(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = _require_module_access(module_uuid, user_id)

    entries = db.get_schedule_entries(module["id"], user_id)
    processed_ids = db.get_processed_source_ids(module["id"], user_id)
    processed_uuids: list[str] = []
    for sid in processed_ids:
        src = db.get_kia_source_by_id(sid)
        if src:
            processed_uuids.append(src["uuid"])

    return {
        "entries": [_serialize_entry(e) for e in entries],
        "processed_source_uuids": processed_uuids,
    }


# ─── GENERATE (async via Celery) ────────────────────────────────────────────

@router.post("/ki-assistent/modules/{module_uuid}/schedule/generate")
async def generate_schedule(
    module_uuid: str,
    body: schemas.ScheduleGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = _require_module_access(module_uuid, user_id)

    if not body.source_ids:
        raise HTTPException(status_code=400, detail="Keine Quellen ausgewählt")

    # Filter: skip already-processed sources client-side already knows this,
    # but we also store the full selection for traceability. The task will
    # filter again on its own.
    job = db.create_schedule_job(module["id"], user_id, list(body.source_ids))

    from src.tasks.kia_tasks import run_generate_schedule
    run_generate_schedule.delay(job["id"], module["id"], user_id, list(body.source_ids))

    return {"job_id": job["id"], "status": "pending"}


@router.get("/ki-assistent/modules/{module_uuid}/schedule/jobs/active")
async def get_active_schedule_job_route(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = _require_module_access(module_uuid, user_id)
    job = db.get_active_schedule_job(module["id"], user_id)
    if not job:
        return {"active": False}
    return {
        "active": True,
        "id": job["id"],
        "status": job["status"],
        "created_at": job["created_at"].isoformat() + "Z" if job.get("created_at") else None,
    }


@router.get("/ki-assistent/modules/{module_uuid}/schedule/jobs/{job_id}")
async def get_schedule_job(
    module_uuid: str,
    job_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    _require_module_access(module_uuid, user_id)
    job = db.get_schedule_job(job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    return {
        "id": job["id"],
        "status": job["status"],
        "error": job.get("error"),
        "added_count": job.get("added_count") or 0,
        "source_uuids": job.get("source_uuids") or [],
        "created_at": job["created_at"].isoformat() + "Z" if job.get("created_at") else None,
        "updated_at": job["updated_at"].isoformat() + "Z" if job.get("updated_at") else None,
    }


# ─── CREATE MANUAL ENTRY ────────────────────────────────────────────────────

@router.post("/ki-assistent/modules/{module_uuid}/schedule/entries")
async def create_entry(
    module_uuid: str,
    body: schemas.ScheduleEntryCreateBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = _require_module_access(module_uuid, user_id)

    if body.type not in ("deadline", "termin"):
        raise HTTPException(status_code=400, detail="Typ muss 'deadline' oder 'termin' sein")

    row = db.create_schedule_entry(
        module["id"],
        user_id,
        type=body.type,
        title=body.title.strip(),
        description=(body.description.strip() if body.description else None),
        due_date=_parse_date(body.due_date),
        due_time=_parse_time(body.due_time),
        is_optional=body.is_optional,
        origin="manual",
        source_refs=[],
    )
    return _serialize_entry(row)


# ─── UPDATE ENTRY ───────────────────────────────────────────────────────────

@router.put("/ki-assistent/modules/{module_uuid}/schedule/entries/{entry_id}")
async def update_entry(
    module_uuid: str,
    entry_id: int,
    body: schemas.ScheduleEntryUpdateBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    _require_module_access(module_uuid, user_id)

    existing = db.get_schedule_entry(entry_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    if body.type is not None and body.type not in ("deadline", "termin"):
        raise HTTPException(status_code=400, detail="Typ muss 'deadline' oder 'termin' sein")

    row = db.update_schedule_entry(
        entry_id,
        user_id,
        type=body.type,
        title=(body.title.strip() if body.title else None),
        description=(body.description.strip() if body.description else None),
        due_date=_parse_date(body.due_date) if body.due_date else None,
        due_time=_parse_time(body.due_time) if body.due_time else None,
        is_optional=body.is_optional,
        is_checked=body.is_checked,
        clear_date=body.clear_date,
        clear_time=body.clear_time,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return _serialize_entry(row)


# ─── DELETE ENTRY ───────────────────────────────────────────────────────────

@router.delete("/ki-assistent/modules/{module_uuid}/schedule/entries/{entry_id}")
async def delete_entry(
    module_uuid: str,
    entry_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    _require_module_access(module_uuid, user_id)
    if not db.delete_schedule_entry(entry_id, user_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"ok": True}


# ─── DELETE ALL ─────────────────────────────────────────────────────────────

@router.delete("/ki-assistent/modules/{module_uuid}/schedule")
async def delete_all(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = _require_module_access(module_uuid, user_id)
    count = db.delete_all_schedule_entries(module["id"], user_id)
    return {"deleted": count}
