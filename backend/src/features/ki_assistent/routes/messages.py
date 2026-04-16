"""KI-Assistent routes — messages + user settings."""

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

@router.delete("/ki-assistent/modules/{module_uuid}/messages")
async def delete_messages(
    module_uuid: str,
    enrollment_id: Optional[int] = None,
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

    eid = enrollment_id if not is_owner else None
    db.delete_ki_tutor_messages(module["id"], user_id, enrollment_id=eid)
    logger.info("KI Tutor: chat cleared for module {} by user {}", module_uuid, user_id)
    return {"cleared": True}

@router.get("/ki-assistent/modules/{module_uuid}/messages")
async def get_messages(
    module_uuid: str,
    enrollment_id: Optional[int] = None,
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

    eid = enrollment_id if not is_owner else None
    messages = db.get_ki_tutor_messages(module["id"], user_id, enrollment_id=eid)
    return [
        {
            "role": m["role"],
            "content": m["content"],
            "source_pages": m["source_pages"],
            "source_qmap": m.get("source_qmap"),
            "created_at": m["created_at"].isoformat() + "Z" if m["created_at"] else None,
        }
        for m in messages
    ]

@router.get("/ki-assistent/modules/{module_uuid}/settings")
async def get_user_settings(
    module_uuid: str,
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

    return db.get_ki_tutor_user_settings(module["id"], user_id)

@router.patch("/ki-assistent/modules/{module_uuid}/settings")
async def update_user_settings(
    module_uuid: str,
    body: schemas.UserSettingsBody,
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

    db.upsert_ki_tutor_user_settings(
        module["id"], user_id, body.chat_lang, body.studio_enabled, body.sprachtraining_active
    )
    return {"ok": True}


# ─── Notizen ─────────────────────────────────────────────────────────────────

