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
    _require_workspace_manage,
    _require_workspace_owner,
    _require_workspace_access,
    _delete_workspace_files,
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

def _parse_optional_expiry(raw: str | None, locale: str) -> datetime | None:
    """Turn an ISO string into a UTC datetime. Empty or missing means never expires."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail=t("date.invalidExpiresAt", locale))


def _managed_workspace_payload(m: dict, access: str, shared: bool) -> dict:
    """Row for someone who manages this workspace, owner or tutor alike.

    Tutors handle enrollment links like the owner: inviting learners does not
    widen the circle of people with rights. What stays with the owner is deleting
    the workspace, which is unrecoverable, and handing out tutor rights.
    """
    sources = db.get_aia_sources_by_workspace(m["id"])
    links = db.get_access_links_by_workspace(m["id"])
    return {
        "uuid": m["uuid"],
        "title": m["title"],
        "description": m["description"],
        "status": m["status"],
        "is_active": m["is_active"],
        "access": access,
        "shared": shared,
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
    }


@router.get("/ai-assistant/workspaces")
async def list_workspaces(current_user: dict = Depends(get_current_user)):
    """Every workspace the user can reach, in one list.

    ``access`` says how they reach it: 'owner', 'tutor' or 'student'. Owners and
    tutors get the full management payload, students the plain one. A workspace
    joined through several student links still appears once per enrollment,
    because those have separate chat histories.
    """
    user_id = current_user["user_id"]
    with_tutors = db.get_workspace_ids_with_tutors()
    result = []

    for m in db.get_aia_workspaces_by_user(user_id):
        result.append(_managed_workspace_payload(m, "owner", m["id"] in with_tutors))

    owned_ids = {m["uuid"] for m in result}
    seen_as_tutor: set[str] = set()
    for m in db.get_aia_workspaces_for_member(user_id):
        if m["uuid"] in owned_ids:
            continue  # owner who also holds an enrollment, ownership already covers it
        if m.get("member_role") == "tutor":
            if m["uuid"] in seen_as_tutor:
                continue  # enrolled through several links, still one workspace
            seen_as_tutor.add(m["uuid"])
            result.append(_managed_workspace_payload(m, "tutor", True))
            continue
        result.append({
            "uuid": m["uuid"],
            "title": m["title"],
            "description": m["description"],
            "status": m["status"],
            "is_active": m["is_active"],
            "access": "student",
            "shared": False,
            "source_count": len(db.get_aia_sources_by_workspace(m["id"])),
            "enrollment_id": m.get("enrollment_id"),
            "enrolled_until": m["enrolled_until"].isoformat() + "Z" if m.get("enrolled_until") else None,
            "created_at": m["created_at"].isoformat() + "Z" if m["created_at"] else None,
        })

    # A student row for a workspace the user also tutors would be a duplicate
    # with fewer rights, so the stronger role wins.
    result = [r for r in result if not (r["access"] == "student" and r["uuid"] in seen_as_tutor)]
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
    is_owner = workspace["user_id"] == current_user["user_id"]
    if is_owner:
        db.touch_aia_workspace_visited(workspace_uuid)
    sources = db.get_aia_sources_by_workspace(workspace["id"])
    links = db.get_access_links_by_workspace(workspace["id"])
    # Tutors manage the workspace like its owner, so the UI follows can_manage.
    # is_owner stays literal ownership, it is not a permission.
    can_manage = is_owner or db.is_workspace_tutor(workspace["id"], current_user["user_id"])
    return {
        "uuid": workspace["uuid"],
        "title": workspace["title"],
        "description": workspace["description"],
        "status": workspace["status"],
        "is_active": workspace["is_active"],
        "is_owner": is_owner,
        "can_manage": can_manage,
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
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    new_title = body.title if body.title is not None else workspace["title"]
    new_desc = body.description if body.description is not None else workspace["description"]
    new_active = body.is_active if body.is_active is not None else workspace["is_active"]
    db.update_aia_workspace(workspace_uuid, new_title, new_desc, new_active)
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
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    expires = _parse_optional_expiry(body.expires_at, locale)
    new_code = uuid.uuid4().hex[:8]
    link = db.create_access_link(workspace["id"], new_code, expires)
    db.set_aia_workspace_enroll_code(workspace_uuid, new_code, expires)
    logger.info("KI Tutor: access link created for workspace {}", workspace_uuid)
    return {
        "enroll_code": new_code,
        "enroll_code_expires": expires.isoformat() + "Z" if expires else None,
        "link_id": link["id"],
    }


# ─── Access Links ────────────────────────────────────────────────────────────

@router.post("/ai-assistant/workspaces/{workspace_uuid}/access-links")
async def create_workspace_access_link(
    workspace_uuid: str,
    body: schemas.CreateAccessLinkBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    existing_links = db.get_access_links_by_workspace(workspace["id"])
    if len(existing_links) >= AIA_WORKSPACE_MAX_ACCESS_LINKS:
        raise HTTPException(
            status_code=400,
            detail=t("ai.workspace.maxAccessLinks", locale, max=AIA_WORKSPACE_MAX_ACCESS_LINKS),
        )
    expires = _parse_optional_expiry(body.expires_at, locale)
    code = uuid.uuid4().hex[:8]
    link = db.create_access_link(workspace["id"], code, expires)
    logger.info("KI Tutor: access link {} created for workspace {}", link["id"], workspace_uuid)
    return {
        "id": link["id"],
        "code": link["code"],
        "expires_at": link["expires_at"].isoformat() + "Z" if link["expires_at"] else None,
    }

@router.get("/ai-assistant/workspaces/{workspace_uuid}/access-links")
async def list_access_links(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    links = db.get_access_links_by_workspace(workspace["id"])
    return [
        {
            "id": l["id"],
            "code": l["code"],
            "expires_at": l["expires_at"].isoformat() + "Z" if l["expires_at"] else None,
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
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    db.delete_access_link(link_id, workspace["id"])
    logger.info("KI Tutor: access link {} deleted from workspace {}", link_id, workspace_uuid)
    return {"deleted": link_id}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}")
def delete_workspace(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_owner(workspace_uuid, current_user["user_id"], locale=locale)
    _delete_workspace_files(workspace)
    db.delete_aia_workspace(workspace_uuid)
    logger.info("KI Tutor: workspace {} deleted by user {}", workspace_uuid, current_user["user_id"])
    return {"deleted": workspace_uuid}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/participants")
async def list_participants(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Who is in this workspace. Owner and tutors may look, only the owner may change."""
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale=locale)
    is_owner = workspace["user_id"] == current_user["user_id"]
    return {
        "can_edit": is_owner,
        "participants": [
            {
                "user_id": p["user_id"],
                "display_name": p["display_name"],
                "username": p["ldap_username"],
                "role": "tutor" if p["is_tutor"] else "student",
                "joined_at": p["joined_at"].isoformat() + "Z" if p["joined_at"] else None,
                "enrolled_until": p["enrolled_until"].isoformat() + "Z" if p["enrolled_until"] else None,
            }
            for p in db.get_workspace_participants(workspace["id"])
        ],
    }


@router.patch("/ai-assistant/workspaces/{workspace_uuid}/participants/{user_id}")
async def set_participant_role(
    workspace_uuid: str,
    user_id: int,
    body: schemas.SetParticipantRoleBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Make a participant a tutor, or take it back. Owner only.

    Deliberately not open to tutors: whoever can promote can grow the circle of
    people with full rights without the owner ever noticing.
    """
    workspace = _require_workspace_owner(workspace_uuid, current_user["user_id"], locale=locale)
    if user_id == workspace["user_id"]:
        # The owner is not a participant and cannot demote themselves into one.
        raise HTTPException(status_code=400, detail=t("workspace.accessDenied", locale))
    geaendert = db.set_participant_role(workspace["id"], user_id, body.role)
    if not geaendert:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    logger.info(
        "KI Tutor: user {} set to {} in workspace {} by owner {}",
        user_id, body.role, workspace_uuid, current_user["user_id"],
    )
    return {"user_id": user_id, "role": body.role}


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
        # The owner following their own link stays the owner, nothing to join.
        if workspace["user_id"] == user_id:
            return {"workspace_uuid": workspace["uuid"], "title": workspace["title"], "enrollment_id": None}
        # Already a member of this workspace? Then the link is a plain redirect.
        # The question is "already in this course", not "already through this
        # link": a course hands out several links over a semester, and asking per
        # link put the same course into the list twice. The existing enrollment
        # keeps its expiry, so a forwarded link cannot quietly extend an access
        # that was meant to run out.
        existing = db.get_enrollment(workspace["id"], user_id)
        if existing:
            return {"workspace_uuid": workspace["uuid"], "title": workspace["title"], "enrollment_id": existing["id"]}
        # Every link joins as a learner. Tutor rights are handed out by the owner
        # afterwards, to a named person, never by following a link.
        enrollment_id = db.enroll_student(
            workspace["id"], user_id, link["expires_at"], link_id=link["id"],
        )
        if not enrollment_id:
            # Already enrolled (race condition) - fetch existing
            existing = db.get_enrollment(workspace["id"], user_id)
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
    """Legacy: only the workspaces the user learns from.

    Superseded by GET /ai-assistant/workspaces, which returns owned, tutored and
    joined workspaces in one list with an ``access`` field. Kept so older clients
    keep working; nothing in the frontend calls it any more.
    """
    workspaces = [
        m for m in db.get_aia_workspaces_for_student(current_user["user_id"])
        if m.get("role", "student") != "tutor"
    ]
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

