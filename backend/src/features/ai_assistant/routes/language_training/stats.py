"""KI-Assistent routes - language_training stats + streak + activities."""

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
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale, t
from src.limits import (
    GLOSSARY_LIMIT,
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
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    count = db.get_glossary_count(workspace["id"])
    return {"count": count, "limit": GLOSSARY_LIMIT}

