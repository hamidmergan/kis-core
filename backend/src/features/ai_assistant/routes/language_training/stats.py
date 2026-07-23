"""KI-Assistent routes - language_training stats + streak + activities."""


from fastapi import APIRouter, Depends, HTTPException


from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.limits import (
    GLOSSARY_LIMIT,
)

from src.features.ai_assistant.routes._helpers import (
    _require_own_workspace,
)

router = APIRouter(tags=["ki-assistent: language-training"])

@router.get("/ai-assistant/workspaces/{workspace_uuid}/streak")
async def get_streak_endpoint(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    streak = db.get_streak(workspace["id"], user_id)
    return streak


# ─── Student Stats ─────────────────────────────────────────────────────────

@router.get("/ai-assistant/workspaces/{workspace_uuid}/stats")
async def get_student_stats_endpoint(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    return db.get_student_stats(workspace["id"], user_id)

@router.get("/ai-assistant/workspaces/{workspace_uuid}/stats/day")
async def get_student_day_stats_endpoint(
    workspace_uuid: str,
    date: str,
    category: str | None = None,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    return db.get_student_day_stats(workspace["id"], user_id, date, category)

@router.get("/ai-assistant/workspaces/{workspace_uuid}/recent-activities")
async def get_recent_activities_endpoint(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    return db.get_recent_activities(workspace["id"], user_id, limit=10)


# ─── Lecturer: Workspace Statistics ────────────────────────────────────────────

@router.get("/ai-assistant/workspaces/{workspace_uuid}/lecturer-stats")
async def get_lecturer_workspace_stats(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    return db.get_aia_workspace_stats(workspace["id"])


# ─── Glossary Count & Limit ───────────────────────────────────────────────────

@router.get("/ai-assistant/workspaces/{workspace_uuid}/glossary-count")
async def get_glossary_count_endpoint(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    count = db.get_glossary_count(workspace["id"], user_id)
    return {"count": count, "limit": GLOSSARY_LIMIT}

