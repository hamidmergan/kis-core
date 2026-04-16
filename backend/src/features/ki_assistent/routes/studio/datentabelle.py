"""KI-Assistent routes — datentabelle."""

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

@router.post("/ki-assistent/modules/{module_uuid}/datentabelle/generate")
async def generate_datentabelle(
    module_uuid: str,
    body: schemas.DatentabelleGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source_ids = _resolve_source_ids(module, body.active_source_ids, max_count=5)

    # Build source map for citations
    source_map: dict[int, dict] = {}
    for idx, suuid in enumerate(body.active_source_ids):
        src = db.get_ki_tutor_source(suuid)
        if src and src["id"] in source_ids:
            source_map[src["id"]] = {"number": idx + 1, "filename": src["filename"], "uuid": suuid}

    datentabelle_id = db.create_ki_tutor_datentabelle(module["id"], user_id, source_ids)

    from src.tasks.ki_tutor_tasks import run_generate_datentabelle
    # Convert int keys to str for JSON serialization
    source_map_str = {str(k): v for k, v in source_map.items()}
    run_generate_datentabelle.delay(datentabelle_id, source_ids, body.active_source_ids, source_map_str)
    return {"datentabelle_id": datentabelle_id, "status": "pending"}

@router.get("/ki-assistent/modules/{module_uuid}/datentabelle/{datentabelle_id}")
async def get_datentabelle(
    module_uuid: str,
    datentabelle_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Poll datentabelle status."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    dt = db.get_ki_tutor_datentabelle(datentabelle_id)
    if not dt or dt["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Datentabelle nicht gefunden")

    return dt

@router.get("/ki-assistent/modules/{module_uuid}/datentabelle")
async def get_latest_datentabelle(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get the most recent datentabelle for a module."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    dt = db.get_latest_ki_tutor_datentabelle(module["id"], user_id)
    return dt or {}

@router.get("/ki-assistent/modules/{module_uuid}/datentabellen")
async def get_datentabellen(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all datentabellen for a module."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    rows = db.get_ki_tutor_datentabellen_by_module(module["id"], user_id)
    return [
        {
            "id": r["id"],
            "title": r["title"] or "Datentabelle",
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
        }
        for r in rows
    ]

@router.delete("/ki-assistent/modules/{module_uuid}/datentabelle/{datentabelle_id}")
async def delete_datentabelle(
    module_uuid: str,
    datentabelle_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    dt = db.get_ki_tutor_datentabelle(datentabelle_id)
    if not dt or dt["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Datentabelle nicht gefunden")
    db.delete_ki_tutor_datentabelle(datentabelle_id)
    return {"ok": True}


# ─── Sprachtraining: Übungen generieren (via Celery) ────────────────────────

