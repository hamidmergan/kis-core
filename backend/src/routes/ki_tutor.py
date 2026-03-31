"""KI Tutor routes – Dozenten- und Studenten-Endpunkte."""

import json
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_kisski_client
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
from src.tool_prompts import TUTOR_SYSTEM_DIRECT, TUTOR_SYSTEM_DIRECT_WITH_CONTEXT, TUTOR_SYSTEM_RAG, TUTOR_POPUP_ACTIONS

router = APIRouter(tags=["ki-tutor"])


def _trace_kisski(kisski, name: str) -> None:
    """Update current Langfuse observation with provider metadata."""
    langfuse_context.update_current_observation(
        metadata={"provider": kisski._provider, "base_url": kisski._base_url, "model": kisski._model},
        name=name,
    )

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md", ".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"}
_MEDIA_EXTENSIONS = {".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"}
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB (audio/video can be large)


def _format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS for citation references."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


@router.get("/ki-tutor/popup-actions")
async def get_popup_actions():
    """Liefert die konfigurierten Popup-Aktionen für den PDF-Viewer."""
    return {
        "actions": [
            {
                "key": a["key"],
                "label": a["label"],
                "icon": a["icon"],
                "prompt": a["prompt"],
                "min_words": a["min_words"],
            }
            for a in TUTOR_POPUP_ACTIONS
        ]
    }


def _require_own_module(module_uuid: str, user_id: int) -> dict:
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    if module["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    return module


def _save_source_file(username: str, module_uuid: str, source_uuid: str, ext: str, data: bytes) -> str:
    key = f"ki-tutor/{username}/{module_uuid}/quellen/{source_uuid}{ext}"
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / "ki-tutor" / username / module_uuid / "quellen"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{source_uuid}{ext}").write_bytes(data)
    return str(dest / f"{source_uuid}{ext}")


def _delete_source_files_for_module(module: dict) -> None:
    sources = db.get_ki_tutor_sources_by_module(module["id"])
    for source in sources:
        try:
            delete_file(source["file_path"])
        except Exception as e:
            logger.warning("KI Tutor: could not delete file {}: {}", source["file_path"], e)


# ─── Pydantic models ──────────────────────────────────────────────────────────

class CreateModuleForm(BaseModel):
    title: str
    description: Optional[str] = None
    expires_at: Optional[str] = None  # ISO datetime string


class PatchModuleBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RenewCodeBody(BaseModel):
    expires_at: str  # ISO datetime string


class CreateAccessLinkBody(BaseModel):
    expires_at: str  # ISO datetime string


class EnrollBody(BaseModel):
    enroll_code: str


class ChatBody(BaseModel):
    question: str
    active_source_ids: Optional[list[str]] = None
    direct_text: Optional[bool] = False  # True = kein RAG, direkt LLM aufrufen
    source_uuid: Optional[str] = None  # Quell-PDF UUID (bei Popup-Aktionen)
    source_filename: Optional[str] = None
    source_page: Optional[int] = None
    source_text: Optional[str] = None  # Markierter Text (für Highlight bei Pill-Click)
    enrollment_id: Optional[int] = None  # Für per-Link Chat-Trennung


class UserSettingsBody(BaseModel):
    chat_lang: str
    studio_enabled: bool = True
    sprachtraining_active: bool


class NoteBody(BaseModel):
    content: str


# ─── Dozenten-Endpunkte ───────────────────────────────────────────────────────

@router.post("/ki-tutor/modules")
async def create_module(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    expires_at: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module_uuid = db.create_ki_tutor_module(user_id, title, description)

    # Create first access link
    from datetime import timedelta
    enroll_code = uuid.uuid4().hex[:8]
    if expires_at:
        try:
            expires = datetime.fromisoformat(expires_at).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Ungültiges Datumsformat für expires_at")
    else:
        expires = datetime.now(timezone.utc) + timedelta(days=30)

    module = db.get_ki_tutor_module(module_uuid)
    link = db.create_access_link(module["id"], enroll_code, expires)
    # Also set legacy fields for backward compat
    db.set_ki_tutor_module_enroll_code(module_uuid, enroll_code, expires)

    logger.info("KI Tutor: module {} created by user {}", module_uuid, user_id)
    return {
        "uuid": module_uuid,
        "title": title,
        "access_links": [{
            "id": link["id"],
            "code": link["code"],
            "expires_at": link["expires_at"].isoformat() + "Z",
        }],
        # Legacy fields
        "enroll_code": enroll_code,
        "enroll_code_expires": expires.isoformat() + "Z",
    }


@router.get("/ki-tutor/modules")
async def list_modules(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    modules = db.get_ki_tutor_modules_by_user(user_id)
    result = []
    for m in modules:
        sources = db.get_ki_tutor_sources_by_module(m["id"])
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
                    "expires_at": l["expires_at"].isoformat() + "Z",
                    "created_at": l["created_at"].isoformat() + "Z" if l["created_at"] else None,
                }
                for l in links
            ],
            # Legacy: first link as enroll_code for backward compat
            "enroll_code": links[0]["code"] if links else m.get("enroll_code"),
            "enroll_code_expires": links[0]["expires_at"].isoformat() + "Z" if links else (
                m["enroll_code_expires"].isoformat() + "Z" if m.get("enroll_code_expires") else None
            ),
            "created_at": m["created_at"].isoformat() + "Z" if m["created_at"] else None,
        })
    return result


@router.get("/ki-tutor/modules/{module_uuid}")
async def get_module(module_uuid: str, current_user: dict = Depends(get_current_user)):
    module = _require_own_module(module_uuid, current_user["user_id"])
    sources = db.get_ki_tutor_sources_by_module(module["id"])
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
                "expires_at": l["expires_at"].isoformat() + "Z",
                "created_at": l["created_at"].isoformat() + "Z" if l["created_at"] else None,
            }
            for l in links
        ],
        "enroll_code": links[0]["code"] if links else module.get("enroll_code"),
        "enroll_code_expires": links[0]["expires_at"].isoformat() + "Z" if links else (
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


@router.patch("/ki-tutor/modules/{module_uuid}")
async def patch_module(
    module_uuid: str,
    body: PatchModuleBody,
    current_user: dict = Depends(get_current_user),
):
    module = _require_own_module(module_uuid, current_user["user_id"])
    new_title = body.title if body.title is not None else module["title"]
    new_desc = body.description if body.description is not None else module["description"]
    new_active = body.is_active if body.is_active is not None else module["is_active"]
    db.update_ki_tutor_module(module_uuid, new_title, new_desc, new_active)
    return {"uuid": module_uuid, "title": new_title, "is_active": new_active}


@router.patch("/ki-tutor/modules/{module_uuid}/renew-code")
async def renew_enroll_code(
    module_uuid: str,
    body: RenewCodeBody,
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
    db.set_ki_tutor_module_enroll_code(module_uuid, new_code, expires)
    logger.info("KI Tutor: access link created for module {}", module_uuid)
    return {"enroll_code": new_code, "enroll_code_expires": expires.isoformat() + "Z", "link_id": link["id"]}


# ─── Access Links ────────────────────────────────────────────────────────────

@router.post("/ki-tutor/modules/{module_uuid}/access-links")
async def create_module_access_link(
    module_uuid: str,
    body: CreateAccessLinkBody,
    current_user: dict = Depends(get_current_user),
):
    module = _require_own_module(module_uuid, current_user["user_id"])
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


@router.get("/ki-tutor/modules/{module_uuid}/access-links")
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


@router.delete("/ki-tutor/modules/{module_uuid}/access-links/{link_id}")
async def delete_access_link(
    module_uuid: str,
    link_id: int,
    current_user: dict = Depends(get_current_user),
):
    _require_own_module(module_uuid, current_user["user_id"])
    db.delete_access_link(link_id)
    logger.info("KI Tutor: access link {} deleted from module {}", link_id, module_uuid)
    return {"deleted": link_id}


@router.delete("/ki-tutor/modules/{module_uuid}")
async def delete_module(module_uuid: str, current_user: dict = Depends(get_current_user)):
    module = _require_own_module(module_uuid, current_user["user_id"])
    _delete_source_files_for_module(module)
    db.delete_ki_tutor_module(module_uuid)
    logger.info("KI Tutor: module {} deleted by user {}", module_uuid, current_user["user_id"])
    return {"deleted": module_uuid}


@router.post("/ki-tutor/modules/{module_uuid}/sources")
async def upload_source(
    module_uuid: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    module = _require_own_module(module_uuid, current_user["user_id"])

    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Nur {', '.join(sorted(_ALLOWED_EXTENSIONS))} erlaubt",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 500 MB)")

    source_uuid = uuid.uuid4().hex
    username = current_user.get("username", "unknown")
    file_path = _save_source_file(username, module_uuid, source_uuid, ext, data)
    file_type = ext.lstrip(".")

    db.create_ki_tutor_source(
        module_id=module["id"],
        uuid=source_uuid,
        filename=file.filename,
        file_path=file_path,
        file_type=file_type,
    )

    from src.tasks.ki_tutor_tasks import run_index_source
    run_index_source.delay(source_uuid)

    logger.info("KI Tutor: source {} ({}) uploaded to module {}", source_uuid, file.filename, module_uuid)
    return {"uuid": source_uuid, "filename": file.filename, "status": "pending"}


@router.delete("/ki-tutor/modules/{module_uuid}/sources/{source_uuid}")
async def delete_source(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    _require_own_module(module_uuid, current_user["user_id"])
    source = db.get_ki_tutor_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")
    try:
        delete_file(source["file_path"])
    except Exception as e:
        logger.warning("KI Tutor: could not delete source file {}: {}", source["file_path"], e)
    db.delete_ki_tutor_source(source_uuid)
    logger.info("KI Tutor: source {} deleted", source_uuid)
    return {"deleted": source_uuid}


# ─── Studenten-Endpunkte ──────────────────────────────────────────────────────

@router.post("/ki-tutor/enroll")
async def enroll(body: EnrollBody, current_user: dict = Depends(get_current_user)):
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


@router.get("/ki-tutor/my-modules")
async def my_modules(current_user: dict = Depends(get_current_user)):
    modules = db.get_ki_tutor_modules_for_student(current_user["user_id"])
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


@router.get("/ki-tutor/modules/{module_uuid}/sources/{source_uuid}/file")
async def stream_source_file(
    module_uuid: str,
    source_uuid: str,
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

    source = db.get_ki_tutor_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    data = get_file(source["file_path"])
    ext = Path(source["filename"]).suffix.lower()
    media_type_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".mp3": "audio/mpeg",
        ".mp4": "video/mp4",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".webm": "video/webm",
    }
    media_type = media_type_map.get(ext, "application/octet-stream")

    headers = {
        "Content-Disposition": f'inline; filename="{source["filename"]}"',
        "Accept-Ranges": "bytes",
    }
    if len(data) > 0:
        headers["Content-Length"] = str(len(data))

    return Response(
        content=data,
        media_type=media_type,
        headers=headers,
    )


@router.post("/ki-tutor/modules/{module_uuid}/chat")
@observe(name="ki-tutor-chat")
async def chat(
    module_uuid: str,
    body: ChatBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    _trace_kisski(kisski, "ki-tutor-chat")
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    # Sync module status: heal stale 'pending' if all sources are actually ready
    if module["status"] != "ready":
        sources_check = db.get_ki_tutor_sources_by_module(module["id"])
        ready_sources = [s for s in sources_check if s["status"] == "ready"]
        if not ready_sources:
            raise HTTPException(status_code=409, detail="Keine indizierten Quellen vorhanden")
        if all(s["status"] == "ready" for s in sources_check):
            db.update_ki_tutor_module_status(module_uuid, "ready")

    # Resolve active_source_ids (UUIDs → DB int ids)
    source_ids: list[int] | None = None
    if body.active_source_ids is not None:
        resolved = []
        for suuid in body.active_source_ids:
            source = db.get_ki_tutor_source(suuid)
            if source and source["module_id"] == module["id"]:
                resolved.append(source["id"])
        source_ids = resolved if resolved else None

    # Embed question & RAG – gleiche Logik für Chat und Popup-Aktionen
    from src.services.ki_tutor_embeddings import get_embedding_provider
    provider = get_embedding_provider()

    # Bei Popup-Aktionen den markierten Text als Query nutzen (bessere Chunk-Treffer)
    embed_text = body.source_text if body.source_text else body.question
    query_vector = provider.embed_one(embed_text)

    # Bei Popup-Aktionen nur in der Quell-Datei suchen
    search_source_ids = source_ids
    if body.source_uuid:
        popup_source = db.get_ki_tutor_source(body.source_uuid)
        if popup_source:
            search_source_ids = [popup_source["id"]]

    # Hybrid Search: Vector + Keyword mit RRF
    chunks = db.hybrid_search_chunks(
        module["id"], embed_text, query_vector,
        source_ids=search_source_ids, limit=20,
    )
    # Debug: welche Seiten hat die Hybrid Search gefunden?
    found_pages = sorted(set(c["page_number"] for c in chunks))
    logger.info("Hybrid Search: {} chunks, Seiten: {}, Query: '{}'", len(chunks), found_pages, embed_text[:80])

    # Source-Diversity: bei mehreren aktiven Quellen sicherstellen,
    # dass jede Quelle mindestens vertreten ist
    if source_ids and len(source_ids) > 1:
        seen_sources: set[int] = set()
        diverse_chunks: list[dict] = []
        remaining: list[dict] = []
        for chunk in chunks:
            if chunk["source_id"] not in seen_sources:
                seen_sources.add(chunk["source_id"])
                diverse_chunks.append(chunk)
            else:
                remaining.append(chunk)
        # Auffüllen mit restlichen Chunks nach Score
        chunks = diverse_chunks + remaining

    # Build source-number mapping (Q1, Q2, ...) for multi-source disambiguation
    all_sources_list = {s["id"]: s for s in db.get_ki_tutor_sources_by_module(module["id"])}
    source_id_to_qnum: dict[int, int] = {}
    source_qmap: list[dict] = []  # [{qnum, uuid, filename}, ...]
    qnum_counter = 0
    for chunk in chunks:
        sid = chunk["source_id"]
        if sid not in source_id_to_qnum:
            qnum_counter += 1
            source_id_to_qnum[sid] = qnum_counter
            src = all_sources_list.get(sid)
            if src:
                source_qmap.append({
                    "qnum": qnum_counter,
                    "uuid": src["uuid"],
                    "filename": src["filename"],
                    "is_media": Path(src["filename"]).suffix.lower() in _MEDIA_EXTENSIONS,
                })

    # Build context (max 16000 chars) — Quellennummer + Seitenzahl/Timestamp pro Chunk
    context_parts: list[str] = []
    context_len = 0
    for chunk in chunks:
        qn = source_id_to_qnum.get(chunk["source_id"], 1)
        if chunk.get("start_time") is not None:
            part = f"[Q{qn}, {_format_timestamp(chunk['start_time'])}]\n{chunk['content']}"
        else:
            part = f"[Q{qn}, S. {chunk['page_number']}]\n{chunk['content']}"
        if context_len + len(part) > 16000:
            break
        context_parts.append(part)
        context_len += len(part)
    context = "\n\n---\n\n".join(context_parts)

    # Popup-Aktionen: User hat Text selbst markiert
    if body.source_text:
        page_ref = f" [S. {body.source_page}]" if body.source_page else ""
        # "Genauer ausführen" braucht RAG-Kontext, die anderen arbeiten nur mit dem markierten Text
        elaborate_prompt = TUTOR_POPUP_ACTIONS[0]["prompt"]
        if body.question.startswith(str(elaborate_prompt)):
            system_prompt = TUTOR_SYSTEM_DIRECT_WITH_CONTEXT
            user_message = f"{body.question}\n\nMarkierter Text (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}\n\nWeiterer Kontext aus dem Dokument:\n{context}"
        else:
            system_prompt = TUTOR_SYSTEM_DIRECT
            user_message = f"{body.question}\n\nText (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}"
    else:
        system_prompt = TUTOR_SYSTEM_RAG
        user_message = f"Frage: {body.question}\n\nQuellen:\n{context}"

    # Build multi-turn messages: system + history + current question
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Resolve enrollment_id for per-link chat separation
    enrollment_id = body.enrollment_id if not is_owner else None

    # Include recent chat history for follow-up questions (skip for popup actions)
    if not body.source_text:
        history = db.get_ki_tutor_messages(module["id"], user_id, limit=10, enrollment_id=enrollment_id)
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    # Build source_pages before streaming so we can send them at the end
    source_pages: list[dict] = []
    is_popup = bool(body.source_text and body.source_uuid and body.source_page)

    if is_popup:
        source_pages.append({
            "source_uuid": body.source_uuid,
            "filename": body.source_filename or "",
            "page_number": body.source_page,
            "source_text": body.source_text,
        })
    else:
        all_sources = {s["id"]: s for s in db.get_ki_tutor_sources_by_module(module["id"])}
        seen: set[tuple] = set()
        for chunk in chunks:
            source = all_sources.get(chunk["source_id"])
            if source:
                key = (source["uuid"], chunk["page_number"])
                if key not in seen:
                    seen.add(key)
                    snippet = (chunk.get("content") or "")[:120].strip()
                    entry = {
                        "source_uuid": source["uuid"],
                        "filename": source["filename"],
                        "page_number": chunk["page_number"],
                        "source_text": snippet,
                    }
                    if chunk.get("start_time") is not None:
                        entry["start_time"] = chunk["start_time"]
                        entry["end_time"] = chunk.get("end_time")
                    source_pages.append(entry)
        source_pages.sort(key=lambda x: x["page_number"])

    def _stream() -> Generator[str, None, None]:
        answer_parts: list[str] = []
        try:
            stream = kisski._client.chat.completions.create(
                model=kisski._model,
                messages=messages,
                temperature=0.2,
                stream=True,
                **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
            )
            for chunk_resp in stream:
                delta = chunk_resp.choices[0].delta if chunk_resp.choices else None
                if delta and delta.content:
                    answer_parts.append(delta.content)
                    yield f"data: {json.dumps({'token': delta.content})}\n\n"
        except Exception as e:
            logger.error("LLM stream error: {}", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        answer = "".join(answer_parts).strip()
        if is_popup:
            suffix = f" [S. {body.source_page}]"
            answer += suffix
            yield f"data: {json.dumps({'token': suffix})}\n\n"

        # Save messages
        db.save_ki_tutor_message(module["id"], user_id, "user", body.question, enrollment_id=enrollment_id)
        db.save_ki_tutor_message(module["id"], user_id, "assistant", answer, source_pages=source_pages, enrollment_id=enrollment_id)

        # Send final metadata event
        yield f"data: {json.dumps({'done': True, 'source_pages': source_pages, 'source_qmap': source_qmap})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/ki-tutor/modules/{module_uuid}/sources/{source_uuid}/toc")
async def get_pdf_toc(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Liefert das gespeicherte Inhaltsverzeichnis aus der DB."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_ki_tutor_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    return {"toc": source.get("toc") or []}


@router.get("/ki-tutor/modules/{module_uuid}/sources/{source_uuid}/summaries")
async def get_paragraph_summaries(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Return page-level summaries for the sidebar."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_ki_tutor_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    status = source.get("summaries_status", "none")

    summaries = db.get_paragraph_summaries_by_source(source["id"])

    by_page: dict[int, str] = {}
    for s in summaries:
        by_page[s["page_number"]] = s["summary"]

    return {
        "status": status,
        "pages": by_page,
    }


@router.post("/ki-tutor/modules/{module_uuid}/sources/{source_uuid}/summaries/generate")
async def trigger_paragraph_summaries(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger paragraph summary generation for a source."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    if module["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_ki_tutor_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")
    if source["file_type"] != "pdf":
        raise HTTPException(status_code=400, detail="Nur für PDF-Dateien verfügbar")

    status = source.get("summaries_status", "none")
    if status == "generating":
        return {"status": "generating"}

    # Delete old summaries so regeneration starts fresh
    db.delete_paragraph_summaries_by_source(source["id"])
    db.update_ki_tutor_source_summaries_status(source_uuid, "generating")

    from src.tasks.ki_tutor_tasks import run_generate_summaries
    run_generate_summaries.delay(source_uuid)
    return {"status": "generating"}


@router.get("/ki-tutor/modules/{module_uuid}/sources/{source_uuid}/search")
async def search_pdf(
    module_uuid: str,
    source_uuid: str,
    q: str,
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

    source = db.get_ki_tutor_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    ext = Path(source["filename"]).suffix.lower()
    if ext != ".pdf":
        return {"matches": [], "page_width": 0, "page_height": 0}

    import fitz  # pymupdf
    import re
    import unicodedata

    # NFC preserves superscript chars (²,³) so they match the PDF text layer
    q_clean = unicodedata.normalize("NFC", q)
    q_clean = re.sub(r"-\r?\n\s*", "", q_clean)  # only line-break hyphens: "Lö-\nsungsansatz" → "Lösungsansatz"
    q_clean = re.sub(r"\s+", " ", q_clean).strip()

    if not q_clean:
        return {"matches": [], "page_width": 0, "page_height": 0}

    data = get_file(source["file_path"])
    doc = fitz.open(stream=data, filetype="pdf")

    matches = []
    page_width = 0.0
    page_height = 0.0

    for page_num in range(doc.page_count):
        pg = doc[page_num]
        if page_width == 0:
            page_width = pg.rect.width
            page_height = pg.rect.height

        found = pg.search_for(q_clean, flags=fitz.TEXT_DEHYPHENATE)
        if not found:
            continue

        # Group rects that belong to the same multi-line match occurrence.
        # pymupdf returns one rect per matched line — consecutive rects
        # within 1.5x line height belong to the same match.
        sorted_found = sorted(found, key=lambda r: (r.y0, r.x0))
        groups: list[list] = [[sorted_found[0]]]
        for rect in sorted_found[1:]:
            prev = groups[-1][-1]
            line_h = max(prev.height, rect.height, 10)
            if rect.y0 - prev.y1 < line_h * 1.5:
                groups[-1].append(rect)
            else:
                groups.append([rect])

        for group in groups:
            matches.append({
                "page": page_num + 1,
                "rects": [{"x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1} for r in group],
            })

    doc.close()
    return {"matches": matches, "page_width": page_width, "page_height": page_height}


@router.get("/ki-tutor/modules/{module_uuid}/sources/{source_uuid}/markdown")
async def convert_source_to_markdown(
    module_uuid: str,
    source_uuid: str,
    force: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Convert a PDF source to Markdown via KISSKI Docling API.

    Before sending to Docling the PDF is pre-processed with PyMuPDF: any invisible
    OCR text layer that lies on top of rasterised image blocks is redacted so that
    Docling never sees it.  Images from the Docling response are saved to storage
    and referenced as proper URLs in the returned Markdown.
    """
    import httpx
    import re
    from src.config import Settings

    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_ki_tutor_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    ext = Path(source["filename"]).suffix.lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="Nur für PDF-Dateien verfügbar")

    md_path = str(Path(source["file_path"]).with_suffix(".md"))

    if not force and file_exists(md_path):
        cached = get_file(md_path).decode("utf-8")
        return {"markdown": cached}

    data = get_file(source["file_path"])

    # Strip OCR text layers that lie inside image regions before sending to Docling
    clean_pdf = _strip_image_text_layer(data)

    s = Settings()
    if not s.kisski_api_key:
        raise HTTPException(status_code=500, detail="KISSKI API Key nicht konfiguriert")

    base_url = s.kisski_base_url.rstrip("/")
    convert_url = f"{base_url}/documents/convert?do_ocr=false&extract_tables_as_images=false"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                convert_url,
                headers={"Authorization": f"Bearer {s.kisski_api_key}", "accept": "application/json"},
                files={"document": (source["filename"], clean_pdf, "application/pdf")},
            )
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPStatusError as e:
        logger.warning("KISSKI Docling API Fehler {}: {} — Fallback auf PyMuPDF", e.response.status_code, e.response.text)
        return _markdown_fallback(data)
    except Exception as e:
        logger.warning("KISSKI Docling API nicht erreichbar: {} — Fallback auf PyMuPDF", e)
        return _markdown_fallback(data)

    markdown: str = result.get("markdown", "")
    logger.info("Docling response: markdown_len={}", len(markdown))

    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=md_path, Body=markdown.encode("utf-8"))
    else:
        Path(md_path).write_text(markdown, encoding="utf-8")

    return {"markdown": markdown}





def _strip_image_text_layer(pdf_bytes: bytes) -> bytes:
    """Remove invisible OCR text layers that lie on top of rasterised image blocks.

    PDFs processed by OCR tools often contain a text layer positioned directly
    over image regions.  This text is technically selectable but visually hidden
    beneath the image.  Docling reads it as regular document text.

    We identify image block regions (type=1 in PyMuPDF's page dict), add a redaction
    annotation over each one, and apply redactions with text removal only — the image
    pixels are preserved.  The cleaned PDF bytes are returned for sending to Docling.
    """
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    redacted = False
    for page_num, page in enumerate(doc, start=1):
        page_dict = page.get_text("dict")
        image_rects = [
            fitz.Rect(block["bbox"])
            for block in page_dict["blocks"]
            if block["type"] == 1
        ]
        if image_rects:
            logger.info("_strip_image_text_layer p{}: {} image regions found", page_num, len(image_rects))
        for rect in image_rects:
            page.add_redact_annot(rect)
            redacted = True
        if image_rects:
            # images=PDF_REDACT_IMAGE_NONE keeps the image pixels, only text is removed
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    result_bytes = doc.tobytes() if redacted else pdf_bytes
    doc.close()
    if not redacted:
        logger.info("_strip_image_text_layer: no image regions found in PDF, sending as-is")
    return result_bytes


def _markdown_fallback(pdf_bytes: bytes) -> dict:
    """Fallback: extract plain text from PDF via PyMuPDF, skipping image regions."""
    import fitz
    clean = _strip_image_text_layer(pdf_bytes)
    doc = fitz.open(stream=clean, filetype="pdf")
    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            pages.append(f"## Seite {i}\n\n{text}")
    doc.close()
    return {"markdown": "\n\n---\n\n".join(pages) or "_Kein lesbarer Text gefunden._"}


@router.delete("/ki-tutor/modules/{module_uuid}/messages")
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


@router.get("/ki-tutor/modules/{module_uuid}/messages")
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
            "created_at": m["created_at"].isoformat() + "Z" if m["created_at"] else None,
        }
        for m in messages
    ]


@router.get("/ki-tutor/modules/{module_uuid}/settings")
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


@router.patch("/ki-tutor/modules/{module_uuid}/settings")
async def update_user_settings(
    module_uuid: str,
    body: UserSettingsBody,
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


@router.get("/ki-tutor/modules/{module_uuid}/notes")
async def get_notes(
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

    notes = db.get_ki_tutor_notes(module["id"], user_id)
    return [
        {
            "id": n["id"],
            "content": n["content"],
            "created_at": n["created_at"].isoformat() + "Z" if n["created_at"] else None,
        }
        for n in notes
    ]


@router.post("/ki-tutor/modules/{module_uuid}/notes")
async def create_note(
    module_uuid: str,
    body: NoteBody,
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

    note = db.create_ki_tutor_note(module["id"], user_id, body.content.strip())
    return {
        "id": note["id"],
        "content": note["content"],
        "created_at": note["created_at"].isoformat() + "Z" if note["created_at"] else None,
    }


@router.delete("/ki-tutor/modules/{module_uuid}/notes/{note_id}")
async def delete_note(
    module_uuid: str,
    note_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    deleted = db.delete_ki_tutor_note(note_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden")
    return {"ok": True}


# ─── Sprachtraining: Glossar ─────────────────────────────────────────────────


class GlossaryGenerateBody(BaseModel):
    active_source_ids: list[str]  # max 3 source UUIDs


class ExerciseGenerateBody(BaseModel):
    active_source_ids: list[str]


def _resolve_source_ids(module: dict, source_uuids: list[str], max_count: int = 3) -> list[int]:
    """Resolve source UUIDs to DB IDs, enforce max count."""
    if len(source_uuids) > max_count:
        raise HTTPException(status_code=400, detail=f"Maximal {max_count} Quellen erlaubt")
    ids = []
    for suuid in source_uuids:
        source = db.get_ki_tutor_source(suuid)
        if source and source["module_id"] == module["id"] and source["status"] == "ready":
            ids.append(source["id"])
    if not ids:
        raise HTTPException(status_code=400, detail="Keine gültigen Quellen ausgewählt")
    return ids


@router.get("/ki-tutor/modules/{module_uuid}/glossary")
async def get_glossary(
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

    entries = db.get_ki_tutor_glossary_by_module(module["id"])
    return {"entries": entries}


@router.post("/ki-tutor/modules/{module_uuid}/glossary/generate")
async def generate_glossary(
    module_uuid: str,
    body: GlossaryGenerateBody,
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

    source_ids = _resolve_source_ids(module, body.active_source_ids)

    from src.tasks.ki_tutor_tasks import run_generate_glossary
    run_generate_glossary.delay(module["id"], source_ids)
    return {"status": "generating"}


@router.delete("/ki-tutor/modules/{module_uuid}/glossary/{entry_id}")
async def delete_glossary_entry_endpoint(
    module_uuid: str,
    entry_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not db.delete_glossary_entry(entry_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"ok": True}


# ─── Glossar: Aus Markierung extrahieren ─────────────────────────────────────

_GLOSSARY_EXTRACT_PROMPT = """Du bist ein Fachsprachen-Experte. Analysiere den markierten Text und extrahiere daraus Fachbegriffe für ein Glossar.

Antworte NUR mit einem JSON-Array:
[
  {
    "term_de": "Deutscher Fachbegriff",
    "term_en": "English translation",
    "definition": "Kurze Definition auf Deutsch (1-2 Sätze)",
    "example_sentence": "Beispielsatz mit dem Begriff"
  }
]

Regeln:
- Nur echte Fachbegriffe extrahieren — KEINE allgemeinen Wörter (und, oder, ist, der, die, das, er, sie, es, etc.)
- Keine Füllwörter, Pronomen, Artikel, Konjunktionen oder Präpositionen
- Maximal 5 Begriffe pro Markierung
- Wenn der Text KEINE Fachbegriffe enthält, antworte mit einem leeren Array: []
- Definition muss präzise und verständlich sein
- Antworte NUR mit dem JSON-Array"""


class GlossaryExtractBody(BaseModel):
    text: str
    source_uuid: str
    page_number: int


@router.post("/ki-tutor/modules/{module_uuid}/glossary/extract")
async def extract_glossary_from_selection(
    module_uuid: str,
    body: GlossaryExtractBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    """Extract glossary terms from a PDF text selection."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    # Check glossary limit
    current_count = db.get_glossary_count(module["id"])
    if current_count >= GLOSSARY_LIMIT:
        return {"added": 0, "message": "Glossar voll (150 / 150) — entferne Begriffe um neue hinzuzufügen."}

    # Truncate to 300 chars
    text = body.text[:300].strip()
    if not text:
        return {"added": 0, "message": "Kein Text markiert."}

    # Find the source
    source = db.get_ki_tutor_source(body.source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Quelle nicht gefunden")

    # Get existing terms to avoid duplicates
    existing = db.get_ki_tutor_glossary_by_module(module["id"])
    existing_terms = {e["term_de"].lower() for e in existing}

    # Ask LLM to extract terms
    try:
        messages = [
            {"role": "system", "content": _GLOSSARY_EXTRACT_PROMPT},
            {"role": "user", "content": f"Markierter Text:\n\n{text}"},
        ]
        response = kisski._client.chat.completions.create(
            model=kisski._model, messages=messages, temperature=0.2,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        terms = json.loads(answer)
        if not isinstance(terms, list):
            return {"added": 0, "message": "Keine Fachbegriffe erkannt."}

        # Filter duplicates and limit
        remaining_slots = GLOSSARY_LIMIT - current_count
        new_entries = []
        for t in terms[:5]:
            if not t.get("term_de"):
                continue
            if t["term_de"].lower() in existing_terms:
                continue
            new_entries.append({
                "term_de": t["term_de"],
                "term_en": t.get("term_en", ""),
                "definition": t.get("definition", ""),
                "example_sentence": t.get("example_sentence", ""),
                "page_number": body.page_number,
            })
            existing_terms.add(t["term_de"].lower())
            if len(new_entries) >= remaining_slots:
                break

        if not new_entries:
            return {"added": 0, "message": "Keine neuen Fachbegriffe erkannt."}

        db.bulk_create_glossary_entries(source["id"], new_entries)
        count = len(new_entries)
        return {
            "added": count,
            "message": f"{count} Begriff{'e' if count > 1 else ''} zum Glossar hinzugefügt.",
            "entries": new_entries,
        }
    except (json.JSONDecodeError, ValueError):
        return {"added": 0, "message": "Keine Fachbegriffe erkannt."}
    except Exception as e:
        logger.error("Glossary extract error: {}", e)
        raise HTTPException(status_code=500, detail="Extraktion fehlgeschlagen")


# ─── Mindmap generieren ──────────────────────────────────────────────────────


class MindmapGenerateBody(BaseModel):
    active_source_ids: list[str]


@router.post("/ki-tutor/modules/{module_uuid}/mindmap/generate")
async def generate_mindmap(
    module_uuid: str,
    body: MindmapGenerateBody,
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


@router.get("/ki-tutor/modules/{module_uuid}/mindmap/{mindmap_id}")
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


@router.get("/ki-tutor/modules/{module_uuid}/mindmap")
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


@router.get("/ki-tutor/modules/{module_uuid}/mindmaps")
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


@router.delete("/ki-tutor/modules/{module_uuid}/mindmap/{mindmap_id}")
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


# ─── Präsentation generieren ─────────────────────────────────────────────────


class PresentationGenerateBody(BaseModel):
    source_uuid: str
    template: str | None = None  # Template name (e.g. "isy", "thl") or None for fallback


def _get_available_templates() -> list[dict]:
    """Scan templates directory for available PPTX templates."""
    import os
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
    templates = []
    for entry in os.scandir(templates_dir):
        if entry.is_dir() and not entry.name.startswith("_"):
            for f in os.scandir(entry.path):
                if f.name.endswith(".pptx"):
                    templates.append({
                        "id": entry.name,
                        "name": entry.name.upper(),
                        "path": f.path,
                    })
                    break
    return templates


def _resolve_template_path(template_id: str | None) -> str | None:
    """Resolve a template ID to its PPTX file path."""
    if not template_id:
        return None
    for t in _get_available_templates():
        if t["id"] == template_id:
            return t["path"]
    return None


@router.get("/ki-tutor/presentation-templates")
async def list_presentation_templates(current_user: dict = Depends(get_current_user)):
    """List available presentation templates."""
    templates = _get_available_templates()
    return [{"id": t["id"], "name": t["name"]} for t in templates]


@router.post("/ki-tutor/modules/{module_uuid}/presentation/generate")
async def generate_presentation(
    module_uuid: str,
    body: PresentationGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    """Queue presentation generation as a background Celery task."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    # Validate source
    source = db.get_ki_tutor_source(body.source_uuid)
    if not source or source["module_id"] != module["id"] or source["status"] != "ready":
        raise HTTPException(status_code=400, detail="Ungültige oder nicht verarbeitete Quelle")

    # Resolve template
    template_path = _resolve_template_path(body.template)

    # Create DB record
    presentation_id = db.create_ki_tutor_presentation(module["id"], user_id, source["id"])

    # Queue Celery task
    from src.tasks.ki_tutor_tasks import run_generate_presentation
    run_generate_presentation.delay(
        presentation_id, source["id"], body.source_uuid,
        template_path=template_path,
    )

    return {"presentation_id": presentation_id, "status": "pending"}


@router.get("/ki-tutor/modules/{module_uuid}/presentation/{presentation_id}")
async def get_presentation(
    module_uuid: str,
    presentation_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Poll presentation generation status."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    pres = db.get_ki_tutor_presentation(presentation_id)
    if not pres or pres["module_id"] != module["id"]:
        raise HTTPException(status_code=404, detail="Präsentation nicht gefunden")

    return {
        "id": pres["id"],
        "status": pres["status"],
        "title": pres["title"],
        "slides": pres["slides"],
        "presenton_id": pres.get("presenton_id"),
        "error": pres["error"],
    }


@router.get("/ki-tutor/modules/{module_uuid}/presentations")
async def get_presentations(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all presentations for this module/user."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    presentations = db.get_ki_tutor_presentations_by_module(module["id"], user_id)
    return [
        {
            "id": p["id"],
            "status": p["status"],
            "title": p["title"],
            "source_filename": p.get("source_filename"),
            "slides": p["slides"],
            "presenton_id": p.get("presenton_id"),
            "error": p["error"],
            "created_at": p["created_at"].isoformat() + "Z" if p.get("created_at") else None,
        }
        for p in presentations
    ]


@router.get("/ki-tutor/modules/{module_uuid}/presentation/{presentation_id}/download")
async def download_presentation(
    module_uuid: str,
    presentation_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Download the generated PPTX file."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    pres = db.get_ki_tutor_presentation(presentation_id)
    if not pres or pres["module_id"] != module["id"]:
        raise HTTPException(status_code=404, detail="Präsentation nicht gefunden")

    if pres["status"] != "success" or not pres.get("pptx_path"):
        raise HTTPException(status_code=400, detail="Präsentation noch nicht fertig")

    from src.storage import get_file
    from urllib.parse import quote
    pptx_data = get_file(pres["pptx_path"])
    title = pres.get("title") or "Praesentation"
    # Sanitize filename for Content-Disposition (ASCII fallback + UTF-8)
    safe_name = title.encode("ascii", "ignore").decode() or "Praesentation"
    safe_name = safe_name.replace('"', "").strip()[:100]

    from starlette.responses import Response
    return Response(
        content=pptx_data,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f"attachment; filename=\"{safe_name}.pptx\"; filename*=UTF-8''{quote(title)}.pptx",
        },
    )


@router.delete("/ki-tutor/modules/{module_uuid}/presentation/{presentation_id}")
async def delete_presentation(
    module_uuid: str,
    presentation_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete a presentation."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    pres = db.get_ki_tutor_presentation(presentation_id)
    if not pres or pres["module_id"] != module["id"] or pres["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Präsentation nicht gefunden")

    # Delete PPTX file if exists
    if pres.get("pptx_path"):
        try:
            from src.storage import delete_file
            delete_file(pres["pptx_path"])
        except Exception:
            pass

    db.delete_ki_tutor_presentation(presentation_id)
    return {"ok": True}


# ─── Infografik generieren ───────────────────────────────────────────────────


class InfographicGenerateBody(BaseModel):
    active_source_ids: list[str]
    style: str = "professional"


@router.post("/ki-tutor/modules/{module_uuid}/infographic/generate")
async def generate_infographic(
    module_uuid: str,
    body: InfographicGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    """Queue infographic generation as a background Celery task."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    if body.style not in ("professional", "scientific", "modern"):
        raise HTTPException(status_code=400, detail="Ungültiger Stil")

    source_ids = _resolve_source_ids(module, body.active_source_ids[:1], max_count=1)

    source_uuids = []
    for suuid in body.active_source_ids[:1]:
        s = db.get_ki_tutor_source(suuid)
        if s and s["id"] in source_ids:
            source_uuids.append(suuid)

    infographic_id = db.create_ki_tutor_infographic(module["id"], user_id, source_ids, body.style)

    from src.tasks.ki_tutor_tasks import run_generate_infographic
    run_generate_infographic.delay(infographic_id, source_ids, source_uuids, body.style)

    return {"infographic_id": infographic_id, "status": "pending"}


@router.get("/ki-tutor/modules/{module_uuid}/infographic/{infographic_id}")
async def get_infographic(
    module_uuid: str,
    infographic_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Poll infographic generation status."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    ig = db.get_ki_tutor_infographic(infographic_id)
    if not ig or ig["module_id"] != module["id"]:
        raise HTTPException(status_code=404, detail="Infografik nicht gefunden")

    return {
        "id": ig["id"],
        "status": ig["status"],
        "title": ig["title"],
        "layout_data": ig["layout_data"],
        "style": ig["style"],
        "error": ig["error"],
    }


@router.get("/ki-tutor/modules/{module_uuid}/infographic")
async def get_latest_infographic(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get the latest infographic for this module."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    ig = db.get_latest_ki_tutor_infographic(module["id"], user_id)
    if not ig:
        return {"id": None, "status": None, "title": None, "layout_data": None, "style": None, "error": None}

    return {
        "id": ig["id"],
        "status": ig["status"],
        "title": ig["title"],
        "layout_data": ig["layout_data"],
        "style": ig["style"],
        "error": ig["error"],
    }


@router.delete("/ki-tutor/modules/{module_uuid}/infographic/{infographic_id}")
async def delete_infographic(
    module_uuid: str,
    infographic_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete an infographic."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    ig = db.get_ki_tutor_infographic(infographic_id)
    if not ig or ig["module_id"] != module["id"] or ig["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Infografik nicht gefunden")

    db.delete_ki_tutor_infographic(infographic_id)
    return {"ok": True}


@router.get("/ki-tutor/modules/{module_uuid}/infographics")
async def list_infographics(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """List all saved infographics for this module."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    rows = db.get_ki_tutor_infographics_by_module(module["id"], user_id)
    return [
        {
            "id": r["id"],
            "title": r["title"] or "Infografik",
            "style": r.get("style", "professional"),
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
        }
        for r in rows
    ]


# ─── Lernkarten generieren ───────────────────────────────────────────────────


class LernkartenGenerateBody(BaseModel):
    active_source_ids: list[str]
    count: int = 10


@router.post("/ki-tutor/modules/{module_uuid}/lernkarten/generate")
@observe(name="ki-tutor-lernkarten")
async def generate_lernkarten(
    module_uuid: str,
    body: LernkartenGenerateBody,
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


class DatentabelleGenerateBody(BaseModel):
    active_source_ids: list[str]


@router.post("/ki-tutor/modules/{module_uuid}/datentabelle/generate")
async def generate_datentabelle(
    module_uuid: str,
    body: DatentabelleGenerateBody,
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

    source_ids = _resolve_source_ids(module, body.active_source_ids, max_count=5)

    # Build source map for citations
    source_map: dict[int, dict] = {}
    for idx, suuid in enumerate(body.active_source_ids):
        src = db.get_ki_tutor_source(suuid)
        if src and src["id"] in source_ids:
            source_map[src["id"]] = {"number": idx + 1, "filename": src["filename"], "uuid": suuid}

    datentabelle_id = db.create_ki_tutor_datentabelle(module["id"], user_id, source_ids)

    from src.tasks.ki_tutor_tasks import run_generate_datentabelle
    # Convert int keys to str for JSON serialization
    source_map_str = {str(k): v for k, v in source_map.items()}
    run_generate_datentabelle.delay(datentabelle_id, source_ids, body.active_source_ids, source_map_str)
    return {"datentabelle_id": datentabelle_id, "status": "pending"}


@router.get("/ki-tutor/modules/{module_uuid}/datentabelle/{datentabelle_id}")
async def get_datentabelle(
    module_uuid: str,
    datentabelle_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Poll datentabelle status."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    dt = db.get_ki_tutor_datentabelle(datentabelle_id)
    if not dt or dt["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Datentabelle nicht gefunden")

    return dt


@router.get("/ki-tutor/modules/{module_uuid}/datentabelle")
async def get_latest_datentabelle(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get the most recent datentabelle for a module."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    dt = db.get_latest_ki_tutor_datentabelle(module["id"], user_id)
    return dt or {}


@router.get("/ki-tutor/modules/{module_uuid}/datentabellen")
async def get_datentabellen(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all datentabellen for a module."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    rows = db.get_ki_tutor_datentabellen_by_module(module["id"], user_id)
    return [
        {
            "id": r["id"],
            "title": r["title"] or "Datentabelle",
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
        }
        for r in rows
    ]


@router.delete("/ki-tutor/modules/{module_uuid}/datentabelle/{datentabelle_id}")
async def delete_datentabelle(
    module_uuid: str,
    datentabelle_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    dt = db.get_ki_tutor_datentabelle(datentabelle_id)
    if not dt or dt["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Datentabelle nicht gefunden")
    db.delete_ki_tutor_datentabelle(datentabelle_id)
    return {"ok": True}


# ─── Sprachtraining: Übungen generieren (via Celery) ────────────────────────


@router.post("/ki-tutor/modules/{module_uuid}/exercises/cloze")
async def generate_cloze(
    module_uuid: str,
    body: ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    """Create a cloze exercise set via Celery."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    entries = db.get_ki_tutor_glossary_by_module(module["id"])
    if not entries:
        raise HTTPException(status_code=400, detail="Kein Glossar vorhanden")

    placeholder = db.create_exercise_set_placeholder(
        module_id=module["id"], user_id=user_id, tool="lueckentext",
        title="Wird generiert…", mode="glossar", source_uuid=None,
    )
    from src.tasks.ki_tutor_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(placeholder["id"], module["id"], "lueckentext", "glossar", 10, None)
    return {"set_id": placeholder["id"], "status": "generating"}


@router.post("/ki-tutor/modules/{module_uuid}/exercises/vocab-test")
async def generate_vocab_test(
    module_uuid: str,
    body: ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    """Create a vocab test exercise set via Celery."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    entries = db.get_ki_tutor_glossary_by_module(module["id"])
    if not entries:
        raise HTTPException(status_code=400, detail="Kein Glossar vorhanden")

    placeholder = db.create_exercise_set_placeholder(
        module_id=module["id"], user_id=user_id, tool="vokabeltest",
        title="Wird generiert…", mode="glossar", source_uuid=None,
    )
    from src.tasks.ki_tutor_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(placeholder["id"], module["id"], "vokabeltest", "glossar", 10, None)
    return {"set_id": placeholder["id"], "status": "generating"}


# ─── Exercise Sets CRUD ──────────────────────────────────────────────────────

GLOSSARY_LIMIT = 150


class CreateSetBody(BaseModel):
    tool: str  # "lernkarten" | "lueckentext" | "vokabeltest"
    mode: str = "glossar"  # "glossar" | "quelle"
    source_uuid: Optional[str] = None
    count: int = 10


class ExerciseProgressBody(BaseModel):
    results: list[dict]  # [{"item_id": int, "correct": bool}]


@router.post("/ki-tutor/modules/{module_uuid}/exercise-sets")
async def create_exercise_set(
    module_uuid: str,
    body: CreateSetBody,
    current_user: dict = Depends(get_current_user),
):
    """Create a new exercise set — returns immediately, generates via Celery."""
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    if body.mode == "quelle" and not body.source_uuid:
        raise HTTPException(status_code=400, detail="Keine Quelle angegeben")

    placeholder = db.create_exercise_set_placeholder(
        module_id=module["id"], user_id=user_id, tool=body.tool,
        title="Wird generiert…", mode=body.mode, source_uuid=body.source_uuid,
    )

    from src.tasks.ki_tutor_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(
        placeholder["id"], module["id"], body.tool, body.mode, body.count, body.source_uuid,
    )

    return {"set": placeholder}


@router.get("/ki-tutor/modules/{module_uuid}/exercise-sets")
async def list_exercise_sets(
    module_uuid: str,
    tool: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    return {"sets": db.get_exercise_sets(module["id"], user_id, tool)}


@router.get("/ki-tutor/modules/{module_uuid}/exercise-sets/{set_id}")
async def get_exercise_set(
    module_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
):
    ex_set = db.get_exercise_set_with_items(set_id)
    if not ex_set:
        raise HTTPException(status_code=404, detail="Set nicht gefunden")
    return {"set": ex_set}


@router.delete("/ki-tutor/modules/{module_uuid}/exercise-sets/{set_id}")
async def delete_exercise_set_endpoint(
    module_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not db.delete_exercise_set(set_id):
        raise HTTPException(status_code=404, detail="Set nicht gefunden")
    return {"ok": True}


@router.post("/ki-tutor/modules/{module_uuid}/exercise-sets/{set_id}/progress")
async def record_set_progress(
    module_uuid: str,
    set_id: int,
    body: ExerciseProgressBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    db.bulk_record_exercise_progress(set_id, user_id, body.results)
    db.update_streak(module["id"], user_id)
    return {"ok": True}


# ─── Streak ──────────────────────────────────────────────────────────────────


@router.get("/ki-tutor/modules/{module_uuid}/streak")
async def get_streak_endpoint(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    streak = db.get_streak(module["id"], user_id)
    return streak


# ─── Student Stats ─────────────────────────────────────────────────────────


@router.get("/ki-tutor/modules/{module_uuid}/stats")
async def get_student_stats_endpoint(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    return db.get_student_stats(module["id"], user_id)


@router.get("/ki-tutor/modules/{module_uuid}/stats/day")
async def get_student_day_stats_endpoint(
    module_uuid: str,
    date: str,
    category: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    return db.get_student_day_stats(module["id"], user_id, date, category)


# ─── Glossar Count & Limit ───────────────────────────────────────────────────


@router.get("/ki-tutor/modules/{module_uuid}/glossary-count")
async def get_glossary_count_endpoint(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    count = db.get_glossary_count(module["id"])
    return {"count": count, "limit": GLOSSARY_LIMIT}
