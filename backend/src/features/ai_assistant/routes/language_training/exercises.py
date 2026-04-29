"""KI-Assistent routes — language_training exercises."""

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
    GLOSSARY_LIMIT,
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

router = APIRouter(tags=["ki-assistent: language-training"])

@router.post("/ai-assistant/modules/{module_uuid}/exercises/cloze")
async def generate_cloze(
    module_uuid: str,
    body: schemas.ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    """Create a cloze exercise set via Celery."""
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

    entries = db.get_aia_glossary_by_module(module["id"])
    if not entries:
        raise HTTPException(status_code=400, detail="Kein Glossary vorhanden")

    placeholder = db.create_exercise_set_placeholder(
        module_id=module["id"], user_id=user_id, tool="lueckentext",
        title="Wird generiert…", mode="glossary", source_uuid=None,
    )
    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(placeholder["id"], module["id"], "lueckentext", "glossary", 10, None)
    return {"set_id": placeholder["id"], "status": "generating"}

@router.post("/ai-assistant/modules/{module_uuid}/exercises/vocab-test")
async def generate_vocab_test(
    module_uuid: str,
    body: schemas.ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    """Create a vocab test exercise set via Celery."""
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

    entries = db.get_aia_glossary_by_module(module["id"])
    if not entries:
        raise HTTPException(status_code=400, detail="Kein Glossary vorhanden")

    placeholder = db.create_exercise_set_placeholder(
        module_id=module["id"], user_id=user_id, tool="vokabeltest",
        title="Wird generiert…", mode="glossary", source_uuid=None,
    )
    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(placeholder["id"], module["id"], "vokabeltest", "glossary", 10, None)
    return {"set_id": placeholder["id"], "status": "generating"}


# ─── Exercise Sets CRUD ──────────────────────────────────────────────────────

@router.post("/ai-assistant/modules/{module_uuid}/exercise-sets")
async def create_exercise_set(
    module_uuid: str,
    body: schemas.CreateSetBody,
    current_user: dict = Depends(get_current_user),
):
    """Create a new exercise set — returns immediately, generates via Celery."""
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

    if body.mode == "source" and not body.source_uuid:
        raise HTTPException(status_code=400, detail="Keine Source angegeben")

    placeholder = db.create_exercise_set_placeholder(
        module_id=module["id"], user_id=user_id, tool=body.tool,
        title="Wird generiert…", mode=body.mode, source_uuid=body.source_uuid,
    )

    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(
        placeholder["id"], module["id"], body.tool, body.mode, body.count, body.source_uuid,
    )

    return {"set": placeholder}

@router.get("/ai-assistant/modules/{module_uuid}/exercise-sets")
async def list_exercise_sets(
    module_uuid: str,
    tool: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_aia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    sets = db.get_exercise_sets(module["id"], user_id, tool)
    for s in sets:
        if s.get("created_at") and hasattr(s["created_at"], "isoformat"):
            s["created_at"] = s["created_at"].isoformat() + "Z"
    return {"sets": sets}

@router.get("/ai-assistant/modules/{module_uuid}/exercise-sets/{set_id}")
async def get_exercise_set(
    module_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
):
    ex_set = db.get_exercise_set_with_items(set_id)
    if not ex_set:
        raise HTTPException(status_code=404, detail="Set nicht gefunden")
    if ex_set.get("created_at") and hasattr(ex_set["created_at"], "isoformat"):
        ex_set["created_at"] = ex_set["created_at"].isoformat() + "Z"
    return {"set": ex_set}

@router.delete("/ai-assistant/modules/{module_uuid}/exercise-sets/{set_id}")
async def delete_exercise_set_endpoint(
    module_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not db.delete_exercise_set(set_id):
        raise HTTPException(status_code=404, detail="Set nicht gefunden")
    return {"ok": True}

@router.post("/ai-assistant/modules/{module_uuid}/exercise-sets/{set_id}/progress")
async def record_set_progress(
    module_uuid: str,
    set_id: int,
    body: schemas.ExerciseProgressBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_aia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    if body.new_run:
        db.start_new_run(set_id)
    db.bulk_record_exercise_progress(set_id, user_id, body.results)
    db.update_streak(module["id"], user_id)
    return {"ok": True}


# ─── Streak ──────────────────────────────────────────────────────────────────

