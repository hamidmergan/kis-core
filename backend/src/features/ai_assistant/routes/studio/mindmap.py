"""KI-Assistent routes - mindmap."""

import io
import json
import re
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_llm_client, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst
from src.limits import (
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
    AIA_WORKSPACE_MAX_ACCESS_LINKS,
    AIA_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file
from src.tool_prompts import (
    AIA_SYSTEM_DIRECT,
    AIA_SYSTEM_DIRECT_WITH_CONTEXT,
    AIA_SYSTEM_RAG,
    AIA_POPUP_ACTIONS,
)

from src.features.ai_assistant.routes._helpers import (
    _trace_llm,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_workspace,
    _save_source_file,
    _delete_source_files_for_workspace,
    _resolve_source_ids,
    _term_appears_in_text,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: studio"])

@router.post("/ai-assistant/workspaces/{workspace_uuid}/mindmap/generate")
async def generate_mindmap(
    workspace_uuid: str,
    body: schemas.MindmapGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue mindmap generation as a background Celery task."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    source_ids = _resolve_source_ids(workspace, body.active_source_ids, max_count=5, locale=locale)

    # Build uuid→id mapping for the task
    source_uuids = []
    for suuid in body.active_source_ids:
        s = db.get_aia_source(suuid)
        if s and s["id"] in source_ids:
            source_uuids.append(suuid)

    # Create DB record
    mindmap_id = db.create_aia_mindmap(workspace["id"], user_id, source_ids)

    # Queue Celery task
    from src.tasks.aia_tasks import run_generate_mindmap
    run_generate_mindmap.delay(mindmap_id, source_ids, source_uuids)

    return {"mindmap_id": mindmap_id, "status": "pending"}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/mindmap/{mindmap_id}")
async def get_mindmap(
    workspace_uuid: str,
    mindmap_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Poll mindmap generation status."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    mindmap = db.get_aia_mindmap(mindmap_id)
    if not mindmap or mindmap["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("mindmap.notFound", locale))

    return {
        "id": mindmap["id"],
        "status": mindmap["status"],
        "mindmap": mindmap["mindmap"],
        "error": mindmap["error"],
    }

@router.get("/ai-assistant/workspaces/{workspace_uuid}/mindmap")
async def get_latest_mindmap(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Get the latest mindmap for this workspace."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    mindmap = db.get_latest_aia_mindmap(workspace["id"], user_id)
    if not mindmap:
        return {"id": None, "status": None, "mindmap": None, "error": None}

    return {
        "id": mindmap["id"],
        "status": mindmap["status"],
        "mindmap": mindmap["mindmap"],
        "error": mindmap["error"],
    }

@router.get("/ai-assistant/workspaces/{workspace_uuid}/mindmaps")
async def list_mindmaps(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """List all saved mindmaps for this workspace."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    rows = db.get_all_aia_mindmaps(workspace["id"], user_id)
    return [
        {
            "id": r["id"],
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
            "topic": r["mindmap"].get("topic", "Mindmap") if r["mindmap"] else "Mindmap",
        }
        for r in rows
    ]

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/mindmap/{mindmap_id}")
async def delete_mindmap(
    workspace_uuid: str,
    mindmap_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Delete a mindmap."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    mindmap = db.get_aia_mindmap(mindmap_id)
    if not mindmap or mindmap["workspace_id"] != workspace["id"] or mindmap["user_id"] != user_id:
        raise HTTPException(status_code=404, detail=t("mindmap.notFound", locale))

    db.delete_aia_mindmap(mindmap_id)
    return {"ok": True}


# ─── Flashcards generieren ───────────────────────────────────────────────────

# ─── Flashcards generieren ───────────────────────────────────────────────────

