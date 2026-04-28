"""KI-Assistent routes — notes."""

import io
import json
import re
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_kisski_client
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
    KIA_NOTE_TITLE,
)

_NOTE_TITLE_SAFETY_CAP = 200


def _generate_and_store_note_title(kisski, note_id: int, user_id: int, content: str) -> None:
    title = _generate_note_title(kisski, content)
    if not title:
        logger.warning("Notiz-Titel: LLM lieferte keinen Titel (note_id={})", note_id)
        return
    try:
        db.update_kia_note_title(note_id, user_id, title)
        logger.info("Notiz-Titel gesetzt (note_id={}): {}", note_id, title)
    except Exception as e:
        logger.warning("Notiz-Titel konnte nicht gespeichert werden (note_id={}): {}", note_id, e)


def _generate_note_title(kisski, content: str) -> Optional[str]:
    snippet = content.strip()
    if not snippet:
        return None
    if len(snippet) > 4000:
        snippet = snippet[:4000]
    try:
        response = kisski._client.with_options(timeout=30.0).chat.completions.create(
            model=kisski._model,
            messages=[
                {"role": "system", "content": KIA_NOTE_TITLE},
                {"role": "user", "content": snippet},
            ],
            temperature=0.2,
            max_tokens=120,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        title = (response.choices[0].message.content or "").strip().strip('"\'').rstrip(".")
    except Exception as e:
        logger.warning("Notiz-Titel konnte nicht generiert werden: {}", e)
        return None
    if not title:
        return None
    title = " ".join(title.split())
    if len(title) > _NOTE_TITLE_SAFETY_CAP:
        title = title[:_NOTE_TITLE_SAFETY_CAP].rstrip()
    return title

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

@router.get("/ki-assistent/modules/{module_uuid}/notes")
async def get_notes(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    notes = db.get_kia_notes(module["id"], user_id)
    return [
        {
            "id": n["id"],
            "title": n.get("title"),
            "content": n["content"],
            "source_uuids": n.get("source_uuids") or [],
            "source_pages": n.get("source_pages") or [],
            "popup_selection": n.get("popup_selection"),
            "created_at": n["created_at"].isoformat() + "Z" if n["created_at"] else None,
        }
        for n in notes
    ]

@router.post("/ki-assistent/modules/{module_uuid}/notes")
async def create_note(
    module_uuid: str,
    body: schemas.NoteBody,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    if db.count_kia_notes(module["id"], user_id) >= KIA_NOTES_MAX_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"Maximal {KIA_NOTES_MAX_PER_USER} Notizen pro Workspace erlaubt. Bitte lösche nicht mehr benötigte Notizen.",
        )

    content = body.content.strip()
    note = db.create_kia_note(
        module["id"], user_id, content, None,
        body.source_uuids, body.source_pages, body.popup_selection,
    )
    if body.auto_title:
        background_tasks.add_task(_generate_and_store_note_title, kisski, note["id"], user_id, content)
    return {
        "id": note["id"],
        "title": note.get("title"),
        "content": note["content"],
        "source_uuids": note.get("source_uuids") or [],
        "source_pages": note.get("source_pages") or [],
        "popup_selection": note.get("popup_selection"),
        "created_at": note["created_at"].isoformat() + "Z" if note["created_at"] else None,
    }

@router.patch("/ki-assistent/modules/{module_uuid}/notes/{note_id}/title")
async def update_note_title(
    module_uuid: str,
    note_id: int,
    body: schemas.NoteTitleBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    updated = db.update_kia_note_title(note_id, user_id, body.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden")
    return {"ok": True}

@router.delete("/ki-assistent/modules/{module_uuid}/notes/{note_id}")
async def delete_note(
    module_uuid: str,
    note_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    deleted = db.delete_kia_note(note_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden")
    return {"ok": True}


# ─── Sprachtraining: Glossar ─────────────────────────────────────────────────

