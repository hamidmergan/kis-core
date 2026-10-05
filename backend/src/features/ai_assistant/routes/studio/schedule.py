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
from src.features.ai_assistant.scheduling import farben

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


def _month_anchor(d: Optional[date], precision: str) -> Optional[date]:
    """With 'month' the first of the month is only the sort key, never a day number."""
    if precision == "month" and d:
        return d.replace(day=1)
    return d


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
        # When set, the appointment runs until this day.
        "end_date": row["end_date"].isoformat() if row.get("end_date") else None,
        "due_time": row["due_time"].strftime("%H:%M") if row.get("due_time") else None,
        # When set, the appointment ends on this day at this time.
        "end_time": row["end_time"].strftime("%H:%M") if row.get("end_time") else None,
        # Gesetzt heisst: Anfang bekannt, Ende ausdruecklich offen ("ab 15.09.").
        "is_open_ended": bool(row.get("is_open_ended")),
        # 'month' = the source named only a month, the view then shows no day
        "date_precision": row.get("date_precision") or "day",
        # Set when the source wrote no year and the system picked it from the running semester.
        "year_assumed": bool(row.get("year_assumed")),
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
        # When set, the appointment runs until this day.
        "end_date": row["end_date"].isoformat() if row.get("end_date") else None,
        "due_time": row["due_time"].strftime("%H:%M") if row.get("due_time") else None,
        # When set, the appointment ends on this day at this time.
        "end_time": row["end_time"].strftime("%H:%M") if row.get("end_time") else None,
        # Gesetzt heisst: Anfang bekannt, Ende ausdruecklich offen ("ab 15.09.").
        "is_open_ended": bool(row.get("is_open_ended")),
        # 'month' = the source named only a month, the view then shows no day
        "date_precision": row.get("date_precision") or "day",
        # Set when the source wrote no year and the system picked it from the running semester.
        "year_assumed": bool(row.get("year_assumed")),
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
    """The next appointments across all course rooms of the person."""
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


def _calendar_groups(user_id: int) -> list[str]:
    """Every group the calendar shows, in a fixed order so the assignment stays stable."""
    rows = db.get_schedule_entries_for_user(user_id, include_checked=True, include_past_open=True)
    keys = {r["workspace_uuid"] or farben.PRIVAT for r in rows}
    return sorted(keys)


def _calendar_colors_payload(user_id: int) -> dict:
    gruppen = _calendar_groups(user_id)
    vorhanden = db.get_calendar_colors(user_id)
    neu = farben.vergeben(gruppen, vorhanden)
    if neu:
        db.set_calendar_colors(user_id, neu, overwrite=False)
        vorhanden = db.get_calendar_colors(user_id)
    return {
        "palette": list(farben.PALETTE),
        "colors": {g: farben.PALETTE[vorhanden[g] % len(farben.PALETTE)] for g in gruppen if g in vorhanden},
    }


@router.get("/ai-assistant/schedule/colors")
def get_calendar_colors(current_user: dict = Depends(get_current_user)):
    """One colour per workspace and for private appointments, free colours are handed out first."""
    return _calendar_colors_payload(current_user["user_id"])


@router.put("/ai-assistant/schedule/colors")
def put_calendar_color(
    body: schemas.CalendarColorBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """A colour another group holds is swapped, so two groups never end up alike."""
    user_id = current_user["user_id"]
    gruppen = _calendar_groups(user_id)
    if body.group not in gruppen or body.color >= len(farben.PALETTE):
        raise HTTPException(status_code=400, detail=t("ai.schedule.invalidColor", locale))
    vorhanden = db.get_calendar_colors(user_id)
    db.set_calendar_colors(user_id, farben.waehlen(gruppen, vorhanden, body.group, body.color))
    return _calendar_colors_payload(user_id)


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

    # The whole selection is stored, the job filters once more itself.
    job = db.create_schedule_job(workspace["id"], user_id, list(body.source_ids))

    from src.features.ai_assistant.scheduling.service import enqueue_task
    enqueue_task("aia.generate_schedule", user_id,
                 args=[job["id"], workspace["id"], user_id, list(body.source_ids)])

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

    precision = body.date_precision if body.date_precision in ("day", "month") else "day"

    row = db.create_schedule_entry(
        workspace["id"],
        user_id,
        type=body.type,
        title=body.title.strip(),
        description=(body.description.strip() if body.description else None),
        due_date=_month_anchor(_parse_date(body.due_date, locale=locale), precision),
        end_date=_parse_date(body.end_date, locale=locale),
        due_time=_parse_time(body.due_time, locale=locale),
        end_time=_parse_time(body.end_time, locale=locale),
        date_precision=precision,
        is_open_ended=body.is_open_ended,
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

    precision = body.date_precision if body.date_precision in ("day", "month") else None
    # Without a stated precision the entry's own applies.
    effective = precision or (existing.get("date_precision") or "day")

    due_date = _month_anchor(
        _parse_date(body.due_date, locale=locale) if body.due_date else None, effective,
    )
    end_date = _parse_date(body.end_date, locale=locale) if body.end_date else None
    # A date the person sets by hand no longer rests on an assumed year.
    year_confirmed = ((due_date is not None and due_date != existing.get("due_date"))
                      or (end_date is not None and end_date != existing.get("end_date")))

    row = db.update_schedule_entry(
        entry_id,
        user_id,
        type=body.type,
        title=(body.title.strip() if body.title else None),
        description=(body.description.strip() if body.description else None),
        due_date=due_date,
        end_date=end_date,
        due_time=_parse_time(body.due_time, locale=locale) if body.due_time else None,
        end_time=_parse_time(body.end_time, locale=locale) if body.end_time else None,
        date_precision=precision,
        is_open_ended=body.is_open_ended,
        is_optional=body.is_optional,
        is_checked=body.is_checked,
        clear_date=body.clear_date,
        clear_time=body.clear_time,
        clear_end_date=body.clear_end_date,
        clear_end_time=body.clear_end_time,
        year_confirmed=year_confirmed,
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
