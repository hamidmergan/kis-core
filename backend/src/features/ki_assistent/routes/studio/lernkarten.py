"""KI-Assistent routes — lernkarten."""

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

@router.post("/ki-assistent/modules/{module_uuid}/lernkarten/generate")
@observe(name="ki-tutor-lernkarten")
async def generate_lernkarten(
    module_uuid: str,
    body: schemas.LernkartenGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    """Create a lernkarten exercise set via Celery."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source_ids = _resolve_source_ids(module, body.active_source_ids, max_count=5)
    first_uuid = body.active_source_ids[0] if body.active_source_ids else None

    placeholder = db.create_exercise_set_placeholder(
        module_id=module["id"], user_id=user_id, tool="lernkarten",
        title="Wird generiert…", mode="quelle", source_uuid=first_uuid,
    )

    from src.tasks.ki_tutor_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(
        placeholder["id"], module["id"], "lernkarten", "quelle", body.count,
        source_uuids=body.active_source_ids[:5],
    )
    return {"set_id": placeholder["id"], "status": "generating"}


# ─── Datentabelle generieren ─────────────────────────────────────────────────

