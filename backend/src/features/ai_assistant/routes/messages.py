"""KI-Assistent routes - messages + user settings."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger


from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t, TRANSCRIPT_LANGUAGES

from src.features.ai_assistant import schemas
from src.features.ai_assistant.routes._workspace_access import _require_workspace_member

router = APIRouter(tags=["ki-assistent: messages"])

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/messages")
def delete_messages(
    workspace_uuid: str,
    enrollment_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_member(workspace_uuid, user_id, locale)
    is_owner = workspace["user_id"] == user_id

    eid = enrollment_id if not is_owner else None
    db.delete_aia_messages(workspace["id"], user_id, enrollment_id=eid)
    logger.info("KI Tutor: chat cleared for workspace {} by user {}", workspace_uuid, user_id)
    return {"cleared": True}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/messages")
def get_messages(
    workspace_uuid: str,
    enrollment_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_member(workspace_uuid, user_id, locale)
    is_owner = workspace["user_id"] == user_id

    eid = enrollment_id if not is_owner else None
    messages = db.get_aia_messages(workspace["id"], user_id, enrollment_id=eid)
    return [
        {
            "role": m["role"],
            "content": m["content"],
            "source_pages": m["source_pages"],
            "source_qmap": m.get("source_qmap"),
            "aborted": bool(m.get("aborted")),
            "failed": bool(m.get("failed")),
            "created_at": m["created_at"].isoformat() + "Z" if m["created_at"] else None,
        }
        for m in messages
    ]

@router.get("/ai-assistant/workspaces/{workspace_uuid}/settings")
def get_user_settings(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_member(workspace_uuid, user_id, locale)

    return db.get_aia_user_settings(workspace["id"], user_id)

@router.patch("/ai-assistant/workspaces/{workspace_uuid}/settings")
def update_user_settings(
    workspace_uuid: str,
    body: schemas.UserSettingsBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_member(workspace_uuid, user_id, locale)

    if body.popup_translate_lang not in TRANSCRIPT_LANGUAGES:
        raise HTTPException(status_code=400, detail=t("ai.userSettings.popupTranslateLangInvalid", locale))

    db.upsert_aia_user_settings(
        workspace["id"], user_id, body.chat_lang, body.studio_enabled,
        body.popup_translate_lang,
    )
    return {"ok": True}


# ─── Notizen ─────────────────────────────────────────────────────────────────

