"""KI-Assistent routes — mindmap."""

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

@router.post("/ki-assistent/modules/{module_uuid}/mindmap/generate")
async def generate_mindmap(
    module_uuid: str,
    body: schemas.MindmapGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    """Queue mindmap generation as a background Celery task."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source_ids = _resolve_source_ids(module, body.active_source_ids, max_count=5)

    # Build uuid→id mapping for the task
    source_uuids = []
    for suuid in body.active_source_ids:
        s = db.get_ki_tutor_source(suuid)
        if s and s["id"] in source_ids:
            source_uuids.append(suuid)

    # Create DB record
    mindmap_id = db.create_ki_tutor_mindmap(module["id"], user_id, source_ids)

    # Queue Celery task
    from src.tasks.ki_tutor_tasks import run_generate_mindmap
    run_generate_mindmap.delay(mindmap_id, source_ids, source_uuids)

    return {"mindmap_id": mindmap_id, "status": "pending"}

@router.get("/ki-assistent/modules/{module_uuid}/mindmap/{mindmap_id}")
async def get_mindmap(
    module_uuid: str,
    mindmap_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Poll mindmap generation status."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    mindmap = db.get_ki_tutor_mindmap(mindmap_id)
    if not mindmap or mindmap["module_id"] != module["id"]:
        raise HTTPException(status_code=404, detail="Mindmap nicht gefunden")

    return {
        "id": mindmap["id"],
        "status": mindmap["status"],
        "mindmap": mindmap["mindmap"],
        "error": mindmap["error"],
    }

@router.get("/ki-assistent/modules/{module_uuid}/mindmap")
async def get_latest_mindmap(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get the latest mindmap for this module."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    mindmap = db.get_latest_ki_tutor_mindmap(module["id"], user_id)
    if not mindmap:
        return {"id": None, "status": None, "mindmap": None, "error": None}

    return {
        "id": mindmap["id"],
        "status": mindmap["status"],
        "mindmap": mindmap["mindmap"],
        "error": mindmap["error"],
    }

@router.get("/ki-assistent/modules/{module_uuid}/mindmaps")
async def list_mindmaps(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """List all saved mindmaps for this module."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    rows = db.get_all_ki_tutor_mindmaps(module["id"], user_id)
    return [
        {
            "id": r["id"],
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
            "topic": r["mindmap"].get("topic", "Mindmap") if r["mindmap"] else "Mindmap",
        }
        for r in rows
    ]

@router.delete("/ki-assistent/modules/{module_uuid}/mindmap/{mindmap_id}")
async def delete_mindmap(
    module_uuid: str,
    mindmap_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete a mindmap."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    mindmap = db.get_ki_tutor_mindmap(mindmap_id)
    if not mindmap or mindmap["module_id"] != module["id"] or mindmap["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Mindmap nicht gefunden")

    db.delete_ki_tutor_mindmap(mindmap_id)
    return {"ok": True}


# ─── Lernkarten generieren ───────────────────────────────────────────────────

# ─── Lernkarten generieren ───────────────────────────────────────────────────

