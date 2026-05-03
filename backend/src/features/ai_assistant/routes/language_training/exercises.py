"""KI-Assistent routes - language_training exercises."""

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

@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercises/cloze")
async def generate_cloze(
    workspace_uuid: str,
    body: schemas.ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a cloze exercise set via Celery."""
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

    entries = db.get_aia_glossary_by_workspace(workspace["id"])
    if not entries:
        raise HTTPException(status_code=400, detail=t("glossary.notProvided", locale))

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool="lueckentext",
        title="Wird generiert…", mode="glossary", source_uuid=None,
    )
    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(placeholder["id"], workspace["id"], "lueckentext", "glossary", 10, None, locale=locale)
    return {"set_id": placeholder["id"], "status": "generating"}

@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercises/vocab-test")
async def generate_vocab_test(
    workspace_uuid: str,
    body: schemas.ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a vocab test exercise set via Celery."""
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

    entries = db.get_aia_glossary_by_workspace(workspace["id"])
    if not entries:
        raise HTTPException(status_code=400, detail=t("glossary.notProvided", locale))

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool="vokabeltest",
        title="Wird generiert…", mode="glossary", source_uuid=None,
    )
    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(placeholder["id"], workspace["id"], "vokabeltest", "glossary", 10, None, locale=locale)
    return {"set_id": placeholder["id"], "status": "generating"}


# ─── Exercise Sets CRUD ──────────────────────────────────────────────────────

@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets")
async def create_exercise_set(
    workspace_uuid: str,
    body: schemas.CreateSetBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a new exercise set - returns immediately, generates via Celery."""
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

    if body.mode == "source" and not body.source_uuid:
        raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool=body.tool,
        title="Wird generiert…", mode=body.mode, source_uuid=body.source_uuid,
    )

    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(
        placeholder["id"], workspace["id"], body.tool, body.mode, body.count, body.source_uuid,
        locale=locale,
    )

    return {"set": placeholder}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets")
async def list_exercise_sets(
    workspace_uuid: str,
    tool: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    sets = db.get_exercise_sets(workspace["id"], user_id, tool)
    for s in sets:
        if s.get("created_at") and hasattr(s["created_at"], "isoformat"):
            s["created_at"] = s["created_at"].isoformat() + "Z"
    return {"sets": sets}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}")
async def get_exercise_set(
    workspace_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    ex_set = db.get_exercise_set_with_items(set_id)
    if not ex_set:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    if ex_set.get("created_at") and hasattr(ex_set["created_at"], "isoformat"):
        ex_set["created_at"] = ex_set["created_at"].isoformat() + "Z"
    return {"set": ex_set}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}")
async def delete_exercise_set_endpoint(
    workspace_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not db.delete_exercise_set(set_id):
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    return {"ok": True}

@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}/progress")
async def record_set_progress(
    workspace_uuid: str,
    set_id: int,
    body: schemas.ExerciseProgressBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if body.new_run:
        db.start_new_run(set_id)
    db.bulk_record_exercise_progress(set_id, user_id, body.results)
    db.update_streak(workspace["id"], user_id)
    return {"ok": True}


# ─── Streak ──────────────────────────────────────────────────────────────────

