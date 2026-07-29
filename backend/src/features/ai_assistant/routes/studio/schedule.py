"""KI-Assistent routes - schedule."""

from datetime import date, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import DEFAULT_LOCALE, get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: studio"])


# ─── Helpers ────────────────────────────────────────────────────────────────

def _require_module_access(workspace_uuid: str, user_id: int, locale: str = DEFAULT_LOCALE) -> dict:
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))
    return workspace


def _parse_date(s: Optional[str], locale: str = DEFAULT_LOCALE) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=t("ai.schedule.invalidDate", locale, value=s))


def _parse_time(s: Optional[str], locale: str = DEFAULT_LOCALE) -> Optional[time]:
    if not s:
        return None
    try:
        parts = s.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail=t("ai.schedule.invalidTime", locale, value=s))


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


# ─── GLOBAL SCHEDULE (across all owned + enrolled workspaces) ─────────────────

def _serialize_global_entry(row: dict) -> dict:
    """Serialize a row enriched with workspace info (owned vs. enrolled)."""
    return {
        "id": row["id"],
        "workspace_uuid": row["workspace_uuid"],
        "module_title": row["module_title"],
        "module_relation": row["module_relation"],
        "type": row["type"],
        "title": row["title"],
        "description": row.get("description"),
        "due_date": row["due_date"].isoformat() if row.get("due_date") else None,
        "due_time": row["due_time"].strftime("%H:%M") if row.get("due_time") else None,
        "is_checked": row["is_checked"],
    }


@router.get("/ai-assistant/schedule/upcoming")
def get_upcoming_schedule(
    limit: Optional[int] = None,
    offset: int = 0,
    include_checked: bool = False,
    only_checked: bool = False,
    include_past_open: bool = False,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Top-N upcoming schedule entries across all the user's workspaces
    (owned + enrolled). Used by the home widget (limit=5) and the global
    overview page (paginated with limit + offset).

    only_checked=True returns the completed-history view (any date).
    include_past_open=True returns all unchecked entries regardless of date,
      so missed deadlines are visible alongside upcoming ones.
    """
    if limit is not None and (limit < 1 or limit > 500):
        raise HTTPException(status_code=400, detail=t("ai.schedule.limitRange", locale))
    if offset < 0:
        raise HTTPException(status_code=400, detail=t("ai.schedule.offsetRange", locale))
    user_id = current_user["user_id"]
    rows = db.get_schedule_entries_for_user(
        user_id, limit=limit, offset=offset,
        include_checked=include_checked, only_checked=only_checked,
        include_past_open=include_past_open,
    )
    return {"entries": [_serialize_global_entry(r) for r in rows]}


# ─── GET ────────────────────────────────────────────────────────────────────

@router.get("/ai-assistant/workspaces/{workspace_uuid}/schedule")
def get_schedule(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_module_access(workspace_uuid, user_id, locale=locale)

    entries = db.get_schedule_entries(workspace["id"], user_id)
    processed_ids = db.get_processed_source_ids(workspace["id"], user_id)
    processed_uuids: list[str] = []
    for sid in processed_ids:
        src = db.get_aia_source_by_id(sid)
        if src:
            processed_uuids.append(src["uuid"])

    return {
        "entries": [_serialize_entry(e) for e in entries],
        "processed_source_uuids": processed_uuids,
    }


# ─── GENERATE (async via Celery) ────────────────────────────────────────────

@router.post("/ai-assistant/workspaces/{workspace_uuid}/schedule/generate")
def generate_schedule(
    workspace_uuid: str,
    body: schemas.ScheduleGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_module_access(workspace_uuid, user_id, locale=locale)

    if not body.source_ids:
        raise HTTPException(status_code=400, detail=t("ai.source.noneSelected", locale))

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    # Filter: skip already-processed sources client-side already knows this,
    # but we also store the full selection for traceability. The task will
    # filter again on its own.
    job = db.create_schedule_job(workspace["id"], user_id, list(body.source_ids))

    from src.tasks.aia_tasks import run_generate_schedule
    run_generate_schedule.delay(job["id"], workspace["id"], user_id, list(body.source_ids))

    return {"job_id": job["id"], "status": "pending"}


@router.get("/ai-assistant/workspaces/{workspace_uuid}/schedule/jobs/active")
def get_active_schedule_job_route(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_module_access(workspace_uuid, user_id, locale=locale)
    job = db.get_active_schedule_job(workspace["id"], user_id)
    if not job:
        return {"active": False}
    return {
        "active": True,
        "id": job["id"],
        "status": job["status"],
        "created_at": job["created_at"].isoformat() + "Z" if job.get("created_at") else None,
    }


@router.get("/ai-assistant/workspaces/{workspace_uuid}/schedule/jobs/{job_id}")
def get_schedule_job(
    workspace_uuid: str,
    job_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    _require_module_access(workspace_uuid, user_id, locale=locale)
    job = db.get_schedule_job(job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
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

@router.post("/ai-assistant/workspaces/{workspace_uuid}/schedule/entries")
def create_entry(
    workspace_uuid: str,
    body: schemas.ScheduleEntryCreateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_module_access(workspace_uuid, user_id, locale=locale)

    if body.type not in ("deadline", "termin"):
        raise HTTPException(status_code=400, detail=t("scheduleEntry.invalidType", locale))

    row = db.create_schedule_entry(
        workspace["id"],
        user_id,
        type=body.type,
        title=body.title.strip(),
        description=(body.description.strip() if body.description else None),
        due_date=_parse_date(body.due_date, locale=locale),
        due_time=_parse_time(body.due_time, locale=locale),
        is_optional=body.is_optional,
        origin="manual",
        source_refs=[],
    )
    return _serialize_entry(row)


# ─── UPDATE ENTRY ───────────────────────────────────────────────────────────

@router.put("/ai-assistant/workspaces/{workspace_uuid}/schedule/entries/{entry_id}")
def update_entry(
    workspace_uuid: str,
    entry_id: int,
    body: schemas.ScheduleEntryUpdateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    _require_module_access(workspace_uuid, user_id, locale=locale)

    existing = db.get_schedule_entry(entry_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail=t("entry.notFound", locale))

    if body.type is not None and body.type not in ("deadline", "termin"):
        raise HTTPException(status_code=400, detail=t("scheduleEntry.invalidType", locale))

    row = db.update_schedule_entry(
        entry_id,
        user_id,
        type=body.type,
        title=(body.title.strip() if body.title else None),
        description=(body.description.strip() if body.description else None),
        due_date=_parse_date(body.due_date, locale=locale) if body.due_date else None,
        due_time=_parse_time(body.due_time, locale=locale) if body.due_time else None,
        is_optional=body.is_optional,
        is_checked=body.is_checked,
        clear_date=body.clear_date,
        clear_time=body.clear_time,
    )
    if not row:
        raise HTTPException(status_code=404, detail=t("entry.notFound", locale))
    return _serialize_entry(row)


# ─── DELETE ENTRY ───────────────────────────────────────────────────────────

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/schedule/entries/{entry_id}")
def delete_entry(
    workspace_uuid: str,
    entry_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    _require_module_access(workspace_uuid, user_id, locale=locale)
    if not db.delete_schedule_entry(entry_id, user_id):
        raise HTTPException(status_code=404, detail=t("entry.notFound", locale))
    return {"ok": True}


# ─── DELETE ALL ─────────────────────────────────────────────────────────────

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/schedule")
def delete_all(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_module_access(workspace_uuid, user_id, locale=locale)
    count = db.delete_all_schedule_entries(workspace["id"], user_id)
    return {"deleted": count}
