"""KI-Assistent routes — module CRUD, access links, enrollment."""

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
    KIA_SOURCE_MAX_PAGES,
    KIA_MODULE_MAX_SOURCES,
    KIA_MODULE_MAX_ACCESS_LINKS,
    KIA_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file
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

router = APIRouter(tags=["ki-assistent: modules"])

@router.post("/ai-assistant/modules")
async def create_module(
    title: str = Form(..., max_length=100),
    description: Optional[str] = Form(None, max_length=300),
    expires_at: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module_uuid = db.create_aia_module(user_id, title, description)

    # Create first access link
    from datetime import timedelta
    enroll_code = uuid.uuid4().hex[:8]
    if expires_at:
        try:
            expires = datetime.fromisoformat(expires_at).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Ungültiges Datumsformat für expires_at")
    else:
        expires = None

    module = db.get_aia_module(module_uuid)
    link = db.create_access_link(module["id"], enroll_code, expires)
    # Also set legacy fields for backward compat
    db.set_aia_module_enroll_code(module_uuid, enroll_code, expires)

    logger.info("KI Tutor: module {} created by user {}", module_uuid, user_id)
    return {
        "uuid": module_uuid,
        "title": title,
        "access_links": [{
            "id": link["id"],
            "code": link["code"],
            "expires_at": (link["expires_at"].isoformat() + "Z") if link["expires_at"] else None,
        }],
        # Legacy fields
        "enroll_code": enroll_code,
        "enroll_code_expires": (expires.isoformat() + "Z") if expires else None,
    }

@router.get("/ai-assistant/modules")
async def list_modules(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    modules = db.get_aia_modules_by_user(user_id)
    result = []
    for m in modules:
        sources = db.get_aia_sources_by_module(m["id"])
        links = db.get_access_links_by_module(m["id"])
        result.append({
            "uuid": m["uuid"],
            "title": m["title"],
            "description": m["description"],
            "status": m["status"],
            "is_active": m["is_active"],
            "source_count": len(sources),
            "access_links": [
                {
                    "id": l["id"],
                    "code": l["code"],
                    "expires_at": l["expires_at"].isoformat() + "Z" if l["expires_at"] else None,
                    "created_at": l["created_at"].isoformat() + "Z" if l["created_at"] else None,
                }
                for l in links
            ],
            # Legacy: first link as enroll_code for backward compat
            "enroll_code": links[0]["code"] if links else m.get("enroll_code"),
            "enroll_code_expires": (links[0]["expires_at"].isoformat() + "Z" if links[0]["expires_at"] else None) if links else (
                m["enroll_code_expires"].isoformat() + "Z" if m.get("enroll_code_expires") else None
            ),
            "created_at": m["created_at"].isoformat() + "Z" if m["created_at"] else None,
        })
    return result

@router.get("/ai-assistant/modules/{module_uuid}")
async def get_module(module_uuid: str, current_user: dict = Depends(get_current_user)):
    module = _require_own_module(module_uuid, current_user["user_id"])
    db.touch_aia_module_visited(module_uuid)
    sources = db.get_aia_sources_by_module(module["id"])
    links = db.get_access_links_by_module(module["id"])
    return {
        "uuid": module["uuid"],
        "title": module["title"],
        "description": module["description"],
        "status": module["status"],
        "is_active": module["is_active"],
        "access_links": [
            {
                "id": l["id"],
                "code": l["code"],
                "expires_at": l["expires_at"].isoformat() + "Z" if l["expires_at"] else None,
                "created_at": l["created_at"].isoformat() + "Z" if l["created_at"] else None,
            }
            for l in links
        ],
        "enroll_code": links[0]["code"] if links else module.get("enroll_code"),
        "enroll_code_expires": (links[0]["expires_at"].isoformat() + "Z" if links[0]["expires_at"] else None) if links else (
            module["enroll_code_expires"].isoformat() + "Z" if module.get("enroll_code_expires") else None
        ),
        "created_at": module["created_at"].isoformat() + "Z" if module["created_at"] else None,
        "sources": [
            {
                "uuid": s["uuid"],
                "filename": s["filename"],
                "status": s["status"],
                "chunk_count": s["chunk_count"],
                "error_message": s.get("error_message"),
                "created_at": s["created_at"].isoformat() + "Z" if s["created_at"] else None,
            }
            for s in sources
        ],
    }

@router.patch("/ai-assistant/modules/{module_uuid}")
async def patch_module(
    module_uuid: str,
    body: schemas.PatchModuleBody,
    current_user: dict = Depends(get_current_user),
):
    module = _require_own_module(module_uuid, current_user["user_id"])
    new_title = body.title if body.title is not None else module["title"]
    new_desc = body.description if body.description is not None else module["description"]
    new_active = body.is_active if body.is_active is not None else module["is_active"]
    db.update_aia_module(module_uuid, new_title, new_desc, new_active)
    return {"uuid": module_uuid, "title": new_title, "is_active": new_active}

@router.patch("/ai-assistant/modules/{module_uuid}/renew-code")
async def renew_enroll_code(
    module_uuid: str,
    body: schemas.RenewCodeBody,
    current_user: dict = Depends(get_current_user),
):
    """Legacy: creates a new access link (kept for backward compat)."""
    module = _require_own_module(module_uuid, current_user["user_id"])
    try:
        expires = datetime.fromisoformat(body.expires_at).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ungültiges Datumsformat für expires_at")
    new_code = uuid.uuid4().hex[:8]
    link = db.create_access_link(module["id"], new_code, expires)
    db.set_aia_module_enroll_code(module_uuid, new_code, expires)
    logger.info("KI Tutor: access link created for module {}", module_uuid)
    return {"enroll_code": new_code, "enroll_code_expires": expires.isoformat() + "Z", "link_id": link["id"]}


# ─── Access Links ────────────────────────────────────────────────────────────

@router.post("/ai-assistant/modules/{module_uuid}/access-links")
async def create_module_access_link(
    module_uuid: str,
    body: schemas.CreateAccessLinkBody,
    current_user: dict = Depends(get_current_user),
):
    module = _require_own_module(module_uuid, current_user["user_id"])
    existing_links = db.get_access_links_by_module(module["id"])
    if len(existing_links) >= KIA_MODULE_MAX_ACCESS_LINKS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximal {KIA_MODULE_MAX_ACCESS_LINKS} Einschreibelinks pro Modul erlaubt. Bitte lösche zuerst einen alten Link.",
        )
    try:
        expires = datetime.fromisoformat(body.expires_at).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ungültiges Datumsformat für expires_at")
    code = uuid.uuid4().hex[:8]
    link = db.create_access_link(module["id"], code, expires)
    logger.info("KI Tutor: access link {} created for module {}", link["id"], module_uuid)
    return {
        "id": link["id"],
        "code": link["code"],
        "expires_at": link["expires_at"].isoformat() + "Z",
    }

@router.get("/ai-assistant/modules/{module_uuid}/access-links")
async def list_access_links(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    module = _require_own_module(module_uuid, current_user["user_id"])
    links = db.get_access_links_by_module(module["id"])
    return [
        {
            "id": l["id"],
            "code": l["code"],
            "expires_at": l["expires_at"].isoformat() + "Z",
            "created_at": l["created_at"].isoformat() + "Z" if l["created_at"] else None,
        }
        for l in links
    ]

@router.delete("/ai-assistant/modules/{module_uuid}/access-links/{link_id}")
async def delete_access_link(
    module_uuid: str,
    link_id: int,
    current_user: dict = Depends(get_current_user),
):
    _require_own_module(module_uuid, current_user["user_id"])
    db.delete_access_link(link_id)
    logger.info("KI Tutor: access link {} deleted from module {}", link_id, module_uuid)
    return {"deleted": link_id}

@router.delete("/ai-assistant/modules/{module_uuid}")
async def delete_module(module_uuid: str, current_user: dict = Depends(get_current_user)):
    module = _require_own_module(module_uuid, current_user["user_id"])
    _delete_source_files_for_module(module)
    db.delete_aia_module(module_uuid)
    logger.info("KI Tutor: module {} deleted by user {}", module_uuid, current_user["user_id"])
    return {"deleted": module_uuid}

@router.post("/ai-assistant/enroll")
async def enroll(body: schemas.EnrollBody, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]

    # Try new access_links table first
    result = db.get_module_by_access_link_code(body.enroll_code)
    if result:
        module, link = result
        # Check if already enrolled for this specific link
        existing = db.get_enrollment(module["id"], user_id, link["id"])
        if existing:
            return {"module_uuid": module["uuid"], "title": module["title"], "enrollment_id": existing["id"]}
        enrollment_id = db.enroll_student(module["id"], user_id, link["expires_at"], link_id=link["id"])
        if not enrollment_id:
            # Already enrolled (race condition) – fetch existing
            existing = db.get_enrollment(module["id"], user_id, link["id"])
            return {"module_uuid": module["uuid"], "title": module["title"], "enrollment_id": existing["id"] if existing else None}
        logger.info("KI Tutor: user {} enrolled in module {} via link {}", user_id, module["uuid"], link["id"])
        return {"module_uuid": module["uuid"], "title": module["title"], "enrollment_id": enrollment_id}

    # Fallback: legacy enroll_code on module
    module = db.get_module_by_enroll_code(body.enroll_code)
    if not module:
        raise HTTPException(status_code=404, detail="Ungültiger oder abgelaufener Einschreibecode")
    if db.is_student_enrolled(module["id"], user_id):
        return {"module_uuid": module["uuid"], "title": module["title"]}
    enrolled_until = module.get("enroll_code_expires")
    db.enroll_student(module["id"], user_id, enrolled_until)
    logger.info("KI Tutor: user {} enrolled in module {} (legacy)", user_id, module["uuid"])
    return {"module_uuid": module["uuid"], "title": module["title"]}

@router.get("/ai-assistant/my-modules")
async def my_modules(current_user: dict = Depends(get_current_user)):
    modules = db.get_aia_modules_for_student(current_user["user_id"])
    return [
        {
            "uuid": m["uuid"],
            "title": m["title"],
            "description": m["description"],
            "status": m["status"],
            "enrollment_id": m.get("enrollment_id"),
            "enrolled_until": m["enrolled_until"].isoformat() + "Z" if m.get("enrolled_until") else None,
            "created_at": m["created_at"].isoformat() + "Z" if m["created_at"] else None,
        }
        for m in modules
    ]

