"""AI assistant routes: private appointments that belong to no workspace."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.dependencies import get_current_user
from src.i18n import DEFAULT_LOCALE, get_locale, t
from src.features.ai_assistant import schemas
from src.features.ai_assistant.repository import schedule as db
from src.features.ai_assistant.routes.studio.schedule import (
    _parse_date,
    _parse_time,
    _serialize_entry,
)

router = APIRouter(tags=["ki-assistent: kalender"])


def _validate_range(
    due_date: date, end_date: Optional[date], locale: str = DEFAULT_LOCALE
) -> None:
    """The end of a span must not lie before its start."""
    if end_date is not None and end_date < due_date:
        raise HTTPException(status_code=400, detail=t("ai.schedule.rangeReversed", locale))


@router.post("/ai-assistant/schedule/entries")
async def create_personal_entry(
    body: schemas.PersonalEntryCreateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    due = _parse_date(body.due_date, locale=locale)
    if due is None:
        raise HTTPException(status_code=400, detail=t("ai.schedule.dateRequired", locale))
    end = _parse_date(body.end_date, locale=locale)
    _validate_range(due, end, locale)
    row = db.create_personal_entry(
        current_user["user_id"],
        title=body.title.strip(),
        description=(body.description.strip() if body.description else None),
        due_date=due,
        end_date=end,
        due_time=_parse_time(body.due_time, locale=locale),
    )
    return _serialize_entry(row)


@router.put("/ai-assistant/schedule/entries/{entry_id}")
async def update_personal_entry(
    entry_id: int,
    body: schemas.PersonalEntryUpdateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    vorhanden = db.get_schedule_entry(entry_id, user_id)
    if not vorhanden or vorhanden.get("workspace_id") is not None:
        raise HTTPException(status_code=404, detail=t("entry.notFound", locale))

    due = _parse_date(body.due_date, locale=locale)
    end = _parse_date(body.end_date, locale=locale)
    if not body.clear_end_date:
        _validate_range(due or vorhanden["due_date"], end or vorhanden.get("end_date"), locale)

    row = db.update_personal_entry(
        entry_id,
        user_id,
        title=(body.title.strip() if body.title else None),
        description=(body.description.strip() if body.description is not None else None),
        due_date=due,
        end_date=end,
        due_time=_parse_time(body.due_time, locale=locale),
        is_checked=body.is_checked,
        clear_end_date=body.clear_end_date,
        clear_time=body.clear_time,
    )
    if not row:
        raise HTTPException(status_code=404, detail=t("entry.notFound", locale))
    return _serialize_entry(row)


@router.delete("/ai-assistant/schedule/entries/{entry_id}")
async def delete_personal_entry(
    entry_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not db.delete_personal_entry(entry_id, current_user["user_id"]):
        raise HTTPException(status_code=404, detail=t("entry.notFound", locale))
    return {"ok": True}
