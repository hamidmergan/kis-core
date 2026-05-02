"""KI-Assistent routes - notes."""

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
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale, t
from src.limits import (
    KIA_SOURCE_MAX_PAGES,
    KIA_WORKSPACE_MAX_SOURCES,
    KIA_WORKSPACE_MAX_ACCESS_LINKS,
    KIA_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file
from src.tool_prompts import (
    KIA_SYSTEM_DIRECT,
    KIA_SYSTEM_DIRECT_WITH_CONTEXT,
    KIA_SYSTEM_RAG,
    KIA_POPUP_ACTIONS,
    KIA_NOTE_TITLE,
)

_NOTE_TITLE_SAFETY_CAP = 200


def _generate_and_store_note_title(llm, note_id: int, user_id: int, content: str) -> None:
    title = _generate_note_title(llm, content)
    if not title:
        logger.warning("Notiz-Titel: LLM lieferte keinen Titel (note_id={})", note_id)
        return
    try:
        db.update_aia_note_title(note_id, user_id, title)
        logger.info("Notiz-Titel gesetzt (note_id={}): {}", note_id, title)
    except Exception as e:
        logger.warning("Notiz-Titel konnte nicht gespeichert werden (note_id={}): {}", note_id, e)


def _generate_note_title(llm, content: str) -> Optional[str]:
    snippet = content.strip()
    if not snippet:
        return None
    if len(snippet) > 4000:
        snippet = snippet[:4000]
    try:
        response = llm._client.with_options(timeout=30.0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system", "content": KIA_NOTE_TITLE},
                {"role": "user", "content": snippet},
            ],
            temperature=0.2,
            max_tokens=120,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
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

router = APIRouter(tags=["ki-assistent: notes"])

@router.get("/ai-assistant/workspaces/{workspace_uuid}/notes")
async def get_notes(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    notes = db.get_aia_notes(workspace["id"], user_id)
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

@router.post("/ai-assistant/workspaces/{workspace_uuid}/notes")
async def create_note(
    workspace_uuid: str,
    body: schemas.NoteBody,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    llm=Depends(get_llm_client),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    if db.count_aia_notes(workspace["id"], user_id) >= KIA_NOTES_MAX_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=t("ai.notes.maxPerWorkspace", locale, max=KIA_NOTES_MAX_PER_USER),
        )

    content = body.content.strip()
    note = db.create_aia_note(
        workspace["id"], user_id, content, None,
        body.source_uuids, body.source_pages, body.popup_selection,
    )
    if body.auto_title:
        background_tasks.add_task(_generate_and_store_note_title, llm, note["id"], user_id, content)
    return {
        "id": note["id"],
        "title": note.get("title"),
        "content": note["content"],
        "source_uuids": note.get("source_uuids") or [],
        "source_pages": note.get("source_pages") or [],
        "popup_selection": note.get("popup_selection"),
        "created_at": note["created_at"].isoformat() + "Z" if note["created_at"] else None,
    }

@router.patch("/ai-assistant/workspaces/{workspace_uuid}/notes/{note_id}/title")
async def update_note_title(
    workspace_uuid: str,
    note_id: int,
    body: schemas.NoteTitleBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    updated = db.update_aia_note_title(note_id, user_id, body.title)
    if not updated:
        raise HTTPException(status_code=404, detail=t("note.notFound", locale))
    return {"ok": True}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/notes/{note_id}")
async def delete_note(
    workspace_uuid: str,
    note_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    deleted = db.delete_aia_note(note_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=t("note.notFound", locale))
    return {"ok": True}


# ─── LanguageTraining: Glossary ─────────────────────────────────────────────────

