"""KI-Assistent routes — sprachtraining stats + streak + activities."""

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
from src.dependencies import get_current_user, get_kisski_client
from src.limits import (
    TUTOR_SOURCE_MAX_PAGES,
    TUTOR_MODULE_MAX_SOURCES,
    TUTOR_MODULE_MAX_ACCESS_LINKS,
    TUTOR_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
from src.tool_prompts import (
    TUTOR_SYSTEM_DIRECT,
    TUTOR_SYSTEM_DIRECT_WITH_CONTEXT,
    TUTOR_SYSTEM_RAG,
    TUTOR_POPUP_ACTIONS,
)

from src.features.ki_assistent.routes._helpers import (
    _trace_kisski,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_module,
    _save_source_file,
    _delete_source_files_for_module,
    _strip_image_text_layer,
    _markdown_fallback,
    _resolve_source_ids,
    _term_appears_in_text,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ki_assistent import schemas

router = APIRouter(tags=["ki-assistent"])

@router.get("/ki-assistent/modules/{module_uuid}/streak")
async def get_streak_endpoint(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    streak = db.get_streak(module["id"], user_id)
    return streak


# ─── Student Stats ─────────────────────────────────────────────────────────

@router.get("/ki-assistent/modules/{module_uuid}/stats")
async def get_student_stats_endpoint(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    return db.get_student_stats(module["id"], user_id)

@router.get("/ki-assistent/modules/{module_uuid}/stats/day")
async def get_student_day_stats_endpoint(
    module_uuid: str,
    date: str,
    category: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    return db.get_student_day_stats(module["id"], user_id, date, category)

@router.get("/ki-assistent/modules/{module_uuid}/recent-activities")
async def get_recent_activities_endpoint(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    return db.get_recent_activities(module["id"], user_id, limit=10)


# ─── Dozent: Module Statistics ───────────────────────────────────────────────

@router.get("/ki-assistent/modules/{module_uuid}/dozent-stats")
async def get_dozent_module_stats(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    module = _require_own_module(module_uuid, current_user["user_id"])
    return db.get_ki_tutor_module_stats(module["id"])


# ─── Glossar Count & Limit ───────────────────────────────────────────────────

@router.get("/ki-assistent/modules/{module_uuid}/glossary-count")
async def get_glossary_count_endpoint(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    count = db.get_glossary_count(module["id"])
    return {"count": count, "limit": GLOSSARY_LIMIT}

