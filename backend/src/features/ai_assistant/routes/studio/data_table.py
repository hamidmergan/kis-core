"""AI assistant routes - data_table."""

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
from src.dependencies import get_current_user, get_kisski_client, is_admin_user
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst
from src.limits import (
    KIA_SOURCE_MAX_PAGES,
    KIA_MODULE_MAX_SOURCES,
    KIA_MODULE_MAX_ACCESS_LINKS,
    KIA_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
from src.tool_prompts import (
    KIA_SYSTEM_DIRECT,
    KIA_SYSTEM_DIRECT_WITH_CONTEXT,
    KIA_SYSTEM_RAG,
    KIA_POPUP_ACTIONS,
)

from src.features.ai_assistant.routes._helpers import (
    _trace_kisski,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_module,
    _save_source_file,
    _delete_source_files_for_module,
    _resolve_source_ids,
    _term_appears_in_text,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: studio"])

@router.post("/ai-assistant/modules/{module_uuid}/data_table/generate")
async def generate_data_table(
    module_uuid: str,
    body: schemas.DataTableGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_aia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    enforce_aia_burst(user_id)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user))

    source_ids = _resolve_source_ids(module, body.active_source_ids, max_count=5)

    # Build source map for citations
    source_map: dict[int, dict] = {}
    for idx, suuid in enumerate(body.active_source_ids):
        src = db.get_aia_source(suuid)
        if src and src["id"] in source_ids:
            source_map[src["id"]] = {"number": idx + 1, "filename": src["filename"], "uuid": suuid}

    data_table_id = db.create_aia_data_table(module["id"], user_id, source_ids)

    from src.tasks.aia_tasks import run_generate_data_table
    # Convert int keys to str for JSON serialization
    source_map_str = {str(k): v for k, v in source_map.items()}
    run_generate_data_table.delay(data_table_id, source_ids, body.active_source_ids, source_map_str)
    return {"data_table_id": data_table_id, "status": "pending"}

@router.get("/ai-assistant/modules/{module_uuid}/data_table/{data_table_id}")
async def get_data_table(
    module_uuid: str,
    data_table_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Poll data_table status."""
    user_id = current_user["user_id"]
    module = db.get_aia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    dt = db.get_aia_data_table(data_table_id)
    if not dt or dt["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="DataTable nicht gefunden")

    return dt

@router.get("/ai-assistant/modules/{module_uuid}/data_table")
async def get_latest_data_table(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get the most recent data_table for a module."""
    user_id = current_user["user_id"]
    module = db.get_aia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    dt = db.get_latest_aia_data_table(module["id"], user_id)
    return dt or {}

@router.get("/ai-assistant/modules/{module_uuid}/data_tables")
async def get_data_tables(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all data_tables for a module."""
    user_id = current_user["user_id"]
    module = db.get_aia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    rows = db.get_aia_data_tables_by_module(module["id"], user_id)
    return [
        {
            "id": r["id"],
            "title": r["title"] or "DataTable",
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
        }
        for r in rows
    ]

@router.delete("/ai-assistant/modules/{module_uuid}/data_table/{data_table_id}")
async def delete_data_table(
    module_uuid: str,
    data_table_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    dt = db.get_aia_data_table(data_table_id)
    if not dt or dt["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="DataTable nicht gefunden")
    db.delete_aia_data_table(data_table_id)
    return {"ok": True}


# ─── LanguageTraining: generate exercises (via Celery) ────────────────────────

