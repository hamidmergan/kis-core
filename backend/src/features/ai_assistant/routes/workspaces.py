"""KI-Assistent routes - workspace CRUD, access links, enrollment."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from loguru import logger


from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t, TRANSCRIPT_LANGUAGES, DEFAULT_DIAGNOSIS_LANGUAGE
from src.limits import (
    AIA_WORKSPACE_MAX_ACCESS_LINKS,
)

from src.features.ai_assistant.routes._helpers import (
    _require_own_workspace,
    _require_workspace_access,
    _delete_source_files_for_workspace,
)
from src.dependencies_rbac import require_workspace_create
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: workspaces"])

@router.post(
    "/ai-assistant/workspaces",
    dependencies=[Depends(require_workspace_create)],
)
async def create_workspace(
    title: str = Form(..., max_length=100),
    description: Optional[str] = Form(None, max_length=300),
    expires_at: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace_uuid = db.create_aia_workspace(user_id, title, description)

    # Create first access link
    enroll_code = uuid.uuid4().hex[:8]
    if expires_at:
        try:
            expires = datetime.fromisoformat(expires_at).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail=t("date.invalidExpiresAt", locale))
    else:
        expires = None

    workspace = db.get_aia_workspace(workspace_uuid)
    link = db.create_access_link(workspace["id"], enroll_code, expires)
    # Also set legacy fields for backward compat
    db.set_aia_workspace_enroll_code(workspace_uuid, enroll_code, expires)

    logger.info("KI Tutor: workspace {} created by user {}", workspace_uuid, user_id)
    return {
        "uuid": workspace_uuid,
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

@router.get("/ai-assistant/workspaces")
async def list_workspaces(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    workspaces = db.get_aia_workspaces_by_user(user_id)
    result = []
    for m in workspaces:
        sources = db.get_aia_sources_by_workspace(m["id"])
        links = db.get_access_links_by_workspace(m["id"])
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

@router.get("/ai-assistant/transcript-languages")
async def list_transcript_languages(
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Languages an owner may translate media transcripts into. Single source of
    truth is i18n.TRANSCRIPT_LANGUAGES; labels come from the shared ``lang.*`` keys."""
    from src.i18n import DEFAULT_TRANSCRIPT_TARGET
    languages = [
        {"id": code, "label": t(f"lang.{meta['deepl']}", locale)}
        for code, meta in TRANSCRIPT_LANGUAGES.items()
    ]
    return {"languages": languages, "default": DEFAULT_TRANSCRIPT_TARGET}


@router.get("/ai-assistant/workspaces/{workspace_uuid}")
async def get_workspace(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_access(workspace_uuid, current_user["user_id"], locale=locale)
    if workspace["user_id"] == current_user["user_id"]:
        db.touch_aia_workspace_visited(workspace_uuid)
    sources = db.get_aia_sources_by_workspace(workspace["id"])
    links = db.get_access_links_by_workspace(workspace["id"])
    return {
        "uuid": workspace["uuid"],
        "title": workspace["title"],
        "description": workspace["description"],
        "status": workspace["status"],
        "is_active": workspace["is_active"],
        "is_owner": workspace["user_id"] == current_user["user_id"],
        "transcript_translation_mode": workspace.get("transcript_translation_mode", "manual"),
        "transcript_default_lang": workspace.get("transcript_default_lang", "both"),
        "transcript_target_lang": workspace.get("transcript_target_lang", "en"),
        "diagnosis_language": workspace.get("diagnosis_language", DEFAULT_DIAGNOSIS_LANGUAGE),
        "staff_note_text": workspace.get("staff_note_text"),
        "staff_note_links": workspace.get("staff_note_links") or [],
        "access_links": [
            {
                "id": l["id"],
                "code": l["code"],
                "expires_at": l["expires_at"].isoformat() + "Z" if l["expires_at"] else None,
                "created_at": l["created_at"].isoformat() + "Z" if l["created_at"] else None,
            }
            for l in links
        ],
        "enroll_code": links[0]["code"] if links else workspace.get("enroll_code"),
        "enroll_code_expires": (links[0]["expires_at"].isoformat() + "Z" if links[0]["expires_at"] else None) if links else (
            workspace["enroll_code_expires"].isoformat() + "Z" if workspace.get("enroll_code_expires") else None
        ),
        "created_at": workspace["created_at"].isoformat() + "Z" if workspace["created_at"] else None,
        "sources": [
            {
                "uuid": s["uuid"],
                "filename": s["filename"],
                "status": s["status"],
                "chunk_count": s["chunk_count"],
                "error_message": s.get("error_message"),
                "progress": s.get("progress"),
                "created_at": s["created_at"].isoformat() + "Z" if s["created_at"] else None,
            }
            for s in sources
        ],
    }

def _dispatch_transcript_retranslation(workspace: dict, target_lang: str) -> None:
    """Re-translate every ready media source in the workspace into ``target_lang``.

    Owner-only path, fired when the workspace target language changes. No-op when
    translation is off or no provider is configured. The task itself skips sources
    whose source language already equals the target and cleans up stale VTTs.
    """
    if workspace.get("transcript_translation_mode", "manual") == "off":
        return
    from src.services import feature_router, aia_chunker
    try:
        binding = feature_router.resolve("transcript_translate")
    except feature_router.FeatureNotConfigured:
        logger.warning(
            "KI Tutor: target changed but transcript_translate not configured (workspace {})",
            workspace["uuid"],
        )
        return
    from src.tasks.aia_tasks import run_translate_transcript
    dispatched = 0
    for s in db.get_aia_sources_by_workspace(workspace["id"]):
        if s.get("status") != "ready" or not aia_chunker.is_media_file(s.get("file_type") or ""):
            continue
        run_translate_transcript.delay(s["uuid"], binding.provider["id"], target_lang)
        dispatched += 1
    logger.info(
        "KI Tutor: dispatched re-translation to '{}' for {} media source(s) in workspace {}",
        target_lang, dispatched, workspace["uuid"],
    )


@router.patch("/ai-assistant/workspaces/{workspace_uuid}")
async def patch_workspace(
    workspace_uuid: str,
    body: schemas.PatchWorkspaceBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    new_title = body.title if body.title is not None else workspace["title"]
    new_desc = body.description if body.description is not None else workspace["description"]
    new_active = body.is_active if body.is_active is not None else workspace["is_active"]
    db.update_aia_workspace(workspace_uuid, new_title, new_desc, new_active)
    if body.transcript_translation_mode is not None:
        if body.transcript_translation_mode not in ("off", "auto", "manual"):
            raise HTTPException(status_code=400, detail=t("ai.workspace.translationModeInvalid", locale))
        db.set_aia_workspace_translation_mode(workspace_uuid, body.transcript_translation_mode)
    if body.transcript_default_lang is not None:
        if body.transcript_default_lang not in ("source", "target", "both"):
            raise HTTPException(status_code=400, detail=t("ai.workspace.transcriptDefaultLangInvalid", locale))
        db.set_aia_workspace_transcript_default_lang(workspace_uuid, body.transcript_default_lang)
    if body.transcript_target_lang is not None:
        if body.transcript_target_lang not in TRANSCRIPT_LANGUAGES:
            raise HTTPException(status_code=400, detail=t("ai.workspace.transcriptTargetLangInvalid", locale))
        prev_target = workspace.get("transcript_target_lang", "en")
        db.set_aia_workspace_transcript_target_lang(workspace_uuid, body.transcript_target_lang)
        # Switching the target re-translates existing media sources into the new
        # language (overwrite-when-ready: the task writes the new VTT, then drops
        # the stale one). Skipped when translation is off or the target is unchanged.
        if body.transcript_target_lang != prev_target:
            _dispatch_transcript_retranslation(workspace, body.transcript_target_lang)
    if body.diagnosis_language is not None:
        if body.diagnosis_language not in TRANSCRIPT_LANGUAGES:
            raise HTTPException(status_code=400, detail=t("ai.workspace.diagnosisLanguageInvalid", locale))
        db.set_aia_workspace_diagnosis_language(workspace_uuid, body.diagnosis_language)
    if body.staff_note_text is not None or body.staff_note_links is not None:
        new_text = body.staff_note_text if body.staff_note_text is not None else workspace.get("staff_note_text")
        new_links_models = body.staff_note_links if body.staff_note_links is not None else []
        new_links = [{"url": l.url, "label": l.label} for l in new_links_models] if body.staff_note_links is not None else (workspace.get("staff_note_links") or [])
        db.set_aia_workspace_staff_note(workspace_uuid, new_text, new_links)
    return {"uuid": workspace_uuid, "title": new_title, "is_active": new_active}

@router.patch("/ai-assistant/workspaces/{workspace_uuid}/renew-code")
async def renew_enroll_code(
    workspace_uuid: str,
    body: schemas.RenewCodeBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Legacy: creates a new access link (kept for backward compat)."""
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    try:
        expires = datetime.fromisoformat(body.expires_at).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail=t("date.invalidExpiresAt", locale))
    new_code = uuid.uuid4().hex[:8]
    link = db.create_access_link(workspace["id"], new_code, expires)
    db.set_aia_workspace_enroll_code(workspace_uuid, new_code, expires)
    logger.info("KI Tutor: access link created for workspace {}", workspace_uuid)
    return {"enroll_code": new_code, "enroll_code_expires": expires.isoformat() + "Z", "link_id": link["id"]}


# ─── Access Links ────────────────────────────────────────────────────────────

@router.post("/ai-assistant/workspaces/{workspace_uuid}/access-links")
async def create_workspace_access_link(
    workspace_uuid: str,
    body: schemas.CreateAccessLinkBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    existing_links = db.get_access_links_by_workspace(workspace["id"])
    if len(existing_links) >= AIA_WORKSPACE_MAX_ACCESS_LINKS:
        raise HTTPException(
            status_code=400,
            detail=t("ai.workspace.maxAccessLinks", locale, max=AIA_WORKSPACE_MAX_ACCESS_LINKS),
        )
    try:
        expires = datetime.fromisoformat(body.expires_at).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail=t("date.invalidExpiresAt", locale))
    code = uuid.uuid4().hex[:8]
    link = db.create_access_link(workspace["id"], code, expires)
    logger.info("KI Tutor: access link {} created for workspace {}", link["id"], workspace_uuid)
    return {
        "id": link["id"],
        "code": link["code"],
        "expires_at": link["expires_at"].isoformat() + "Z",
    }

@router.get("/ai-assistant/workspaces/{workspace_uuid}/access-links")
async def list_access_links(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    links = db.get_access_links_by_workspace(workspace["id"])
    return [
        {
            "id": l["id"],
            "code": l["code"],
            "expires_at": l["expires_at"].isoformat() + "Z",
            "created_at": l["created_at"].isoformat() + "Z" if l["created_at"] else None,
        }
        for l in links
    ]

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/access-links/{link_id}")
async def delete_access_link(
    workspace_uuid: str,
    link_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    db.delete_access_link(link_id, workspace["id"])
    logger.info("KI Tutor: access link {} deleted from workspace {}", link_id, workspace_uuid)
    return {"deleted": link_id}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}")
async def delete_workspace(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
    _delete_source_files_for_workspace(workspace)
    db.delete_aia_workspace(workspace_uuid)
    logger.info("KI Tutor: workspace {} deleted by user {}", workspace_uuid, current_user["user_id"])
    return {"deleted": workspace_uuid}

@router.get("/ai-assistant/access-link/preview")
async def preview_access_link(
    code: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    result = db.get_workspace_by_access_link_code(code)
    if result:
        workspace, _link = result
        return {"workspace_uuid": workspace["uuid"], "title": workspace["title"]}
    workspace = db.get_workspace_by_enroll_code(code)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("ai.workspace.invalidEnrollCode", locale))
    return {"workspace_uuid": workspace["uuid"], "title": workspace["title"]}

@router.post("/ai-assistant/enroll")
async def enroll(
    body: schemas.EnrollBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]

    # Try new access_links table first
    result = db.get_workspace_by_access_link_code(body.enroll_code)
    if result:
        workspace, link = result
        # Check if already enrolled for this specific link
        existing = db.get_enrollment(workspace["id"], user_id, link["id"])
        if existing:
            return {"workspace_uuid": workspace["uuid"], "title": workspace["title"], "enrollment_id": existing["id"]}
        enrollment_id = db.enroll_student(workspace["id"], user_id, link["expires_at"], link_id=link["id"])
        if not enrollment_id:
            # Already enrolled (race condition) - fetch existing
            existing = db.get_enrollment(workspace["id"], user_id, link["id"])
            return {"workspace_uuid": workspace["uuid"], "title": workspace["title"], "enrollment_id": existing["id"] if existing else None}
        logger.info("KI Tutor: user {} enrolled in workspace {} via link {}", user_id, workspace["uuid"], link["id"])
        return {"workspace_uuid": workspace["uuid"], "title": workspace["title"], "enrollment_id": enrollment_id}

    # Fallback: legacy enroll_code on workspace
    workspace = db.get_workspace_by_enroll_code(body.enroll_code)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("ai.workspace.invalidEnrollCode", locale))
    if db.is_student_enrolled(workspace["id"], user_id):
        return {"workspace_uuid": workspace["uuid"], "title": workspace["title"]}
    enrolled_until = workspace.get("enroll_code_expires")
    db.enroll_student(workspace["id"], user_id, enrolled_until)
    logger.info("KI Tutor: user {} enrolled in workspace {} (legacy)", user_id, workspace["uuid"])
    return {"workspace_uuid": workspace["uuid"], "title": workspace["title"]}

@router.get("/ai-assistant/my-workspaces")
async def my_workspaces(current_user: dict = Depends(get_current_user)):
    workspaces = db.get_aia_workspaces_for_student(current_user["user_id"])
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
        for m in workspaces
    ]

