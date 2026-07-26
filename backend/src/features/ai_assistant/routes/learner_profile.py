"""Student-facing learner-profile routes. Weaknesses are scoped to a workspace, so
the profile view and the "clear all" delete take a workspace in the path. The language
level and the tracking on/off switch are global per user (path without workspace)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t

router = APIRouter(tags=["ki-assistent: learner-profile"])


class EnabledBody(BaseModel):
    enabled: bool


def _require_workspace_access(workspace_uuid: str, user_id: int, locale: str) -> dict:
    """Owner or enrolled student only, same gate as the other workspace routes."""
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] != user_id and not db.is_student_enrolled(workspace["id"], user_id):
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))
    return workspace


@router.get("/ai-assistant/workspaces/{workspace_uuid}/learner-profile")
async def get_learner_profile(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_access(workspace_uuid, user_id, locale)
    ll = db.get_user_language_level(user_id)
    return {
        "enabled": db.is_learning_profile_enabled(user_id),
        "level": ll["language_level"],
        "level_set_at": ll["language_level_set_at"].isoformat() if ll["language_level_set_at"] else None,
        "weaknesses": db.get_learner_weaknesses(user_id, workspace["id"]),
    }


@router.delete("/ai-assistant/learner-profile/weaknesses/{weakness_id}")
async def delete_one(weakness_id: int, current_user: dict = Depends(get_current_user)):
    # By id and owner: a user can only ever remove their own weakness, so this stays
    # global (the id already pins the workspace).
    ok = db.delete_learner_weakness(weakness_id, current_user["user_id"])
    return {"deleted": ok}


@router.delete("/ai-assistant/workspaces/{workspace_uuid}/learner-profile/weaknesses")
async def delete_all(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_access(workspace_uuid, user_id, locale)
    return {"deleted": db.delete_all_learner_weaknesses(user_id, workspace["id"])}


@router.put("/ai-assistant/learner-profile/enabled")
async def set_enabled(body: EnabledBody, current_user: dict = Depends(get_current_user)):
    db.set_learning_profile_enabled(current_user["user_id"], body.enabled)
    return {"enabled": body.enabled}
