"""KI Tutor routes – Dozenten- und Studenten-Endpunkte."""

import json
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_kisski_client
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
from src.tool_prompts import TUTOR_SYSTEM_DIRECT, TUTOR_SYSTEM_DIRECT_WITH_CONTEXT, TUTOR_SYSTEM_RAG, TUTOR_POPUP_ACTIONS, TUTOR_MINDMAP_PROMPT, TUTOR_LERNKARTEN_PROMPT, TUTOR_DATENTABELLE_PROMPT

router = APIRouter(tags=["ki-tutor"])


def _trace_kisski(kisski, name: str) -> None:
    """Update current Langfuse observation with provider metadata."""
    langfuse_context.update_current_observation(
        metadata={"provider": kisski._provider, "base_url": kisski._base_url, "model": kisski._model},
        name=name,
    )

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


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


def _save_source_file(module_uuid: str, source_uuid: str, ext: str, data: bytes) -> str:
    key = f"ki-tutor/{module_uuid}/{source_uuid}{ext}"
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / "ki-tutor" / module_uuid
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

    enroll_code = uuid.uuid4().hex[:8]
    expires: datetime | None = None
    if expires_at:
        try:
            expires = datetime.fromisoformat(expires_at).replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Ungültiges Datumsformat für expires_at")
    else:
        from datetime import timedelta
        expires = datetime.now(timezone.utc) + timedelta(days=30)

    db.set_ki_tutor_module_enroll_code(module_uuid, enroll_code, expires)
    logger.info("KI Tutor: module {} created by user {}", module_uuid, user_id)
    return {
        "uuid": module_uuid,
        "title": title,
        "enroll_code": enroll_code,
        "enroll_code_expires": expires.isoformat(),
    }


@router.get("/ki-tutor/modules")
async def list_modules(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    modules = db.get_ki_tutor_modules_by_user(user_id)
    result = []
    for m in modules:
        sources = db.get_ki_tutor_sources_by_module(m["id"])
        result.append({
            "uuid": m["uuid"],
            "title": m["title"],
            "description": m["description"],
            "status": m["status"],
            "is_active": m["is_active"],
            "source_count": len(sources),
            "enroll_code": m["enroll_code"],
            "enroll_code_expires": m["enroll_code_expires"].isoformat() if m["enroll_code_expires"] else None,
            "created_at": m["created_at"].isoformat() if m["created_at"] else None,
        })
    return result


@router.get("/ki-tutor/modules/{module_uuid}")
async def get_module(module_uuid: str, current_user: dict = Depends(get_current_user)):
    module = _require_own_module(module_uuid, current_user["user_id"])
    sources = db.get_ki_tutor_sources_by_module(module["id"])
    return {
        "uuid": module["uuid"],
        "title": module["title"],
        "description": module["description"],
        "status": module["status"],
        "is_active": module["is_active"],
        "enroll_code": module["enroll_code"],
        "enroll_code_expires": module["enroll_code_expires"].isoformat() if module["enroll_code_expires"] else None,
        "created_at": module["created_at"].isoformat() if module["created_at"] else None,
        "sources": [
            {
                "uuid": s["uuid"],
                "filename": s["filename"],
                "status": s["status"],
                "chunk_count": s["chunk_count"],
                "error_message": s.get("error_message"),
                "created_at": s["created_at"].isoformat() if s["created_at"] else None,
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
    _require_own_module(module_uuid, current_user["user_id"])
    try:
        expires = datetime.fromisoformat(body.expires_at).replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ungültiges Datumsformat für expires_at")
    new_code = uuid.uuid4().hex[:8]
    db.set_ki_tutor_module_enroll_code(module_uuid, new_code, expires)
    logger.info("KI Tutor: enroll code renewed for module {}", module_uuid)
    return {"enroll_code": new_code, "enroll_code_expires": expires.isoformat()}


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
        raise HTTPException(status_code=413, detail="Datei zu groß (max 100 MB)")

    source_uuid = uuid.uuid4().hex
    file_path = _save_source_file(module_uuid, source_uuid, ext, data)
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
    module = db.get_module_by_enroll_code(body.enroll_code)
    if not module:
        raise HTTPException(status_code=404, detail="Ungültiger oder abgelaufener Einschreibecode")

    if db.is_student_enrolled(module["id"], user_id):
        return {"module_uuid": module["uuid"], "title": module["title"]}

    enrolled_until = module["enroll_code_expires"]
    db.enroll_student(module["id"], user_id, enrolled_until)
    logger.info("KI Tutor: user {} enrolled in module {}", user_id, module["uuid"])
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
            "created_at": m["created_at"].isoformat() if m["created_at"] else None,
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
    }
    media_type = media_type_map.get(ext, "application/octet-stream")

    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{source["filename"]}"'},
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
                source_qmap.append({"qnum": qnum_counter, "uuid": src["uuid"], "filename": src["filename"]})

    # Build context (max 16000 chars) — Quellennummer + Seitenzahl pro Chunk
    context_parts: list[str] = []
    context_len = 0
    for chunk in chunks:
        qn = source_id_to_qnum.get(chunk["source_id"], 1)
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

    # Include recent chat history for follow-up questions (skip for popup actions)
    if not body.source_text:
        history = db.get_ki_tutor_messages(module["id"], user_id, limit=10)
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
                    source_pages.append({
                        "source_uuid": source["uuid"],
                        "filename": source["filename"],
                        "page_number": chunk["page_number"],
                        "source_text": snippet,
                    })
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
        db.save_ki_tutor_message(module["id"], user_id, "user", body.question)
        db.save_ki_tutor_message(module["id"], user_id, "assistant", answer, source_pages=source_pages)

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

    summaries = db.get_paragraph_summaries_by_source(source["id"])

    by_page: dict[int, str] = {}
    for s in summaries:
        by_page[s["page_number"]] = s["summary"]

    return {
        "status": source.get("summaries_status", "none"),
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

    db.delete_ki_tutor_messages(module["id"], user_id)
    logger.info("KI Tutor: chat cleared for module {} by user {}", module_uuid, user_id)
    return {"cleared": True}


@router.get("/ki-tutor/modules/{module_uuid}/messages")
async def get_messages(
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

    messages = db.get_ki_tutor_messages(module["id"], user_id)
    return [
        {
            "role": m["role"],
            "content": m["content"],
            "source_pages": m["source_pages"],
            "created_at": m["created_at"].isoformat() if m["created_at"] else None,
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
            "created_at": n["created_at"].isoformat() if n["created_at"] else None,
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
        "created_at": note["created_at"].isoformat() if note["created_at"] else None,
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


_GLOSSARY_PROMPT = """Du bist ein Fachsprachen-Experte. Extrahiere die wichtigsten Fachbegriffe aus dem folgenden Text.

Für jeden Begriff gib EXAKT dieses JSON-Format zurück (als JSON-Array):
[
  {
    "term_de": "Deutscher Fachbegriff",
    "term_en": "English translation",
    "definition": "Kurze Definition auf Deutsch (1-2 Sätze)",
    "example_sentence": "Ein Beispielsatz aus dem Text, der den Begriff verwendet",
    "page_number": 5
  }
]

Regeln:
- Extrahiere 10-20 Fachbegriffe (die wichtigsten und häufigsten)
- Nur echte Fachbegriffe, keine allgemeinen Wörter
- Definition muss präzise und verständlich sein (B1-B2 Niveau)
- example_sentence muss ein echter Satz aus dem gegebenen Text sein
- page_number ist die Seitenzahl, auf der der Begriff vorkommt
- Antworte NUR mit dem JSON-Array, kein anderer Text"""


class VocabProgressBody(BaseModel):
    results: list[dict]  # [{glossary_entry_id, exercise_type, correct}]


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
@observe(name="ki-tutor-glossary")
async def generate_glossary(
    module_uuid: str,
    body: GlossaryGenerateBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    _trace_kisski(kisski, "ki-tutor-glossary")
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source_ids = _resolve_source_ids(module, body.active_source_ids)

    # Gather chunks from all selected sources
    all_chunks: list[dict] = []
    for sid in source_ids:
        all_chunks.extend(db.get_chunks_by_source(sid))
    if not all_chunks:
        raise HTTPException(status_code=400, detail="Keine Chunks vorhanden")

    # Build context (max ~12000 chars)
    context_parts: list[str] = []
    context_len = 0
    for chunk in all_chunks:
        part = f"[S. {chunk['page_number']}]\n{chunk['content']}"
        if context_len + len(part) > 12000:
            break
        context_parts.append(part)
        context_len += len(part)
    context = "\n\n---\n\n".join(context_parts)

    messages = [
        {"role": "system", "content": _GLOSSARY_PROMPT},
        {"role": "user", "content": f"Extrahiere Fachbegriffe aus folgendem Text:\n\n{context}"},
    ]

    try:
        response = kisski._client.chat.completions.create(
            model=kisski._model,
            messages=messages,
            temperature=0.1,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content.strip()

        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        entries_raw = json.loads(answer)
        if not isinstance(entries_raw, list):
            raise ValueError("Expected JSON array")

        # Delete old glossary for these sources, then create new
        for sid in source_ids:
            db.delete_ki_tutor_glossary(sid)

        # Store entries against the first source (primary)
        entries = db.bulk_create_glossary_entries(source_ids[0], entries_raw)
        return {"entries": entries}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Glossary parse error: {} — raw: {}", e, answer[:500] if answer else "empty")
        raise HTTPException(status_code=500, detail="Glossar konnte nicht generiert werden")
    except Exception as e:
        logger.error("Glossary generation error: {}", e)
        raise HTTPException(status_code=500, detail="Glossar-Generierung fehlgeschlagen")


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
    kisski=Depends(get_kisski_client),
):
    _trace_kisski(kisski, "ki-tutor-lernkarten")
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source_ids = _resolve_source_ids(module, body.active_source_ids, max_count=5)

    # Build context with fair budget per source
    budget_per_source = 16000 // len(source_ids)
    context_parts: list[str] = []
    for i, sid in enumerate(source_ids, 1):
        source = None
        for suuid in body.active_source_ids:
            s = db.get_ki_tutor_source(suuid)
            if s and s["id"] == sid:
                source = s
                break
        source_label = source["filename"] if source else f"Quelle {i}"
        summaries = db.get_paragraph_summaries_by_source(sid)
        if summaries:
            pages: dict[int, list[str]] = {}
            for s in summaries:
                pages.setdefault(s["page_number"], []).append(s["summary"])
            parts = [f"[{source_label}, S. {p}] {' '.join(texts)}" for p, texts in sorted(pages.items())]
            part = f"--- {source_label} ---\n" + "\n".join(parts)
        else:
            chunks = db.get_chunks_by_source(sid)
            if chunks:
                parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks[:20]]
                part = f"--- {source_label} ---\n" + "\n".join(parts)
            else:
                continue
        if len(part) > budget_per_source:
            part = part[:budget_per_source]
        context_parts.append(part)

    if not context_parts:
        raise HTTPException(status_code=400, detail="Keine Inhalte vorhanden")

    context = "\n\n".join(context_parts)
    prompt = TUTOR_LERNKARTEN_PROMPT.replace("{count}", str(body.count))

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Erstelle Lernkarten aus folgenden Quellen:\n\n{context}"},
    ]

    try:
        response = kisski._client.chat.completions.create(
            model=kisski._model,
            messages=messages,
            temperature=0.3,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content.strip()

        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        lernkarten = json.loads(answer)
        if not isinstance(lernkarten, dict) or "cards" not in lernkarten:
            raise ValueError("Expected JSON object with 'cards' key")

        return {"lernkarten": lernkarten}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Lernkarten parse error: {} — raw: {}", e, answer[:500] if answer else "empty")
        raise HTTPException(status_code=500, detail="Lernkarten konnten nicht generiert werden")
    except Exception as e:
        logger.error("Lernkarten generation error: {}", e)
        raise HTTPException(status_code=500, detail="Lernkarten-Generierung fehlgeschlagen")


# ─── Datentabelle generieren ─────────────────────────────────────────────────


class DatentabelleGenerateBody(BaseModel):
    active_source_ids: list[str]


@router.post("/ki-tutor/modules/{module_uuid}/datentabelle/generate")
@observe(name="ki-tutor-datentabelle")
async def generate_datentabelle(
    module_uuid: str,
    body: DatentabelleGenerateBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    _trace_kisski(kisski, "ki-tutor-datentabelle")
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source_ids = _resolve_source_ids(module, body.active_source_ids, max_count=5)

    # Build context with source numbering for citations
    source_map: dict[int, dict] = {}
    for idx, suuid in enumerate(body.active_source_ids):
        src = db.get_ki_tutor_source(suuid)
        if src and src["id"] in source_ids:
            source_map[src["id"]] = {"number": idx + 1, "filename": src["filename"], "uuid": suuid}

    context_parts: list[str] = []
    context_len = 0
    for sid in source_ids:
        chunks = db.get_chunks_by_source(sid)
        qnum = source_map.get(sid, {}).get("number", 1)
        for chunk in chunks:
            part = f"[Q{qnum}, S. {chunk['page_number']}]\n{chunk['content']}"
            if context_len + len(part) > 15000:
                break
            context_parts.append(part)
            context_len += len(part)

    if not context_parts:
        raise HTTPException(status_code=400, detail="Keine Chunks vorhanden")

    context = "\n\n---\n\n".join(context_parts)

    # Build source legend for prompt
    source_legend = "\n".join(
        f"[Q{info['number']}] = {info['filename']}"
        for info in sorted(source_map.values(), key=lambda x: x["number"])
    )

    messages = [
        {"role": "system", "content": TUTOR_DATENTABELLE_PROMPT},
        {
            "role": "user",
            "content": (
                f"Quellen:\n{source_legend}\n\n"
                f"Erstelle eine strukturierte Datentabelle aus folgendem Text:\n\n{context}"
            ),
        },
    ]

    try:
        response = kisski._client.chat.completions.create(
            model=kisski._model,
            messages=messages,
            temperature=0.2,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content.strip()

        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        table_data = json.loads(answer)
        if not isinstance(table_data, dict) or "columns" not in table_data or "rows" not in table_data:
            raise ValueError("Expected JSON with 'columns' and 'rows'")

        # Attach source info for frontend
        sources_list = [
            {"number": info["number"], "filename": info["filename"]}
            for info in sorted(source_map.values(), key=lambda x: x["number"])
        ]

        return {"table": table_data, "sources": sources_list}
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Datentabelle parse error: {} — raw: {}", e, answer[:500] if answer else "empty")
        raise HTTPException(status_code=500, detail="Datentabelle konnte nicht generiert werden")
    except Exception as e:
        logger.error("Datentabelle generation error: {}", e)
        raise HTTPException(status_code=500, detail="Datentabelle-Generierung fehlgeschlagen")


# ─── Sprachtraining: Übungen generieren ──────────────────────────────────────


_CLOZE_PROMPT = """Du bist ein Sprachtrainer. Erstelle Lückentext-Übungen aus den gegebenen Fachbegriffen und dem Textkontext.

Für jeden Begriff erstelle EINE Lückentext-Aufgabe im folgenden JSON-Format:
[
  {
    "glossary_entry_id": 42,
    "sentence": "Ein __________ wandelt Wechselstrom in Gleichstrom um.",
    "answer": "Gleichrichter",
    "options": ["Transformator", "Gleichrichter", "Kondensator", "Widerstand"],
    "page_number": 14
  }
]

Regeln:
- Verwende echte Sätze aus dem Kontext oder paraphrasiere sie leicht
- Der Lückentext muss den Fachbegriff als Antwort haben
- Gib genau 4 Optionen, die korrekte Antwort muss enthalten sein
- Die falschen Optionen müssen plausibel sein (gleiche Wortart, ähnliches Themenfeld)
- Antworte NUR mit dem JSON-Array"""


_VOCAB_TEST_PROMPT = """Du bist ein Sprachtrainer. Erstelle einen Vokabeltest zu den gegebenen Fachbegriffen.

Für jeden Begriff erstelle EINE Multiple-Choice-Frage im folgenden JSON-Format:
[
  {
    "glossary_entry_id": 42,
    "question": "Was bedeutet 'Impedance' auf Deutsch?",
    "options": ["Kapazität", "Impedanz", "Induktivität", "Leitfähigkeit"],
    "correct_index": 1,
    "explanation": "Impedanz ist der Wechselstromwiderstand eines Bauteils. (S. 23)"
  }
]

Regeln:
- Mische die Fragerichtungen: DE→EN, EN→DE, Begriff→Definition, Definition→Begriff
- Gib genau 4 Optionen pro Frage
- correct_index ist der 0-basierte Index der richtigen Antwort
- explanation enthält eine kurze Erklärung mit Seitenverweis
- Antworte NUR mit dem JSON-Array"""


@router.post("/ki-tutor/modules/{module_uuid}/exercises/cloze")
@observe(name="ki-tutor-cloze")
async def generate_cloze(
    module_uuid: str,
    body: ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    _trace_kisski(kisski, "ki-tutor-cloze")
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source_ids = _resolve_source_ids(module, body.active_source_ids)

    entries = db.get_ki_tutor_glossary_by_module(module["id"])
    if not entries:
        raise HTTPException(status_code=400, detail="Kein Glossar vorhanden")

    # Get chunks from selected sources for context
    all_chunks: list[dict] = []
    for sid in source_ids:
        all_chunks.extend(db.get_chunks_by_source(sid))
    context_parts = [f"[S. {c['page_number']}] {c['content']}" for c in all_chunks[:15]]
    context = "\n\n".join(context_parts)

    glossary_info = json.dumps([
        {"id": e["id"], "term_de": e["term_de"], "term_en": e["term_en"],
         "definition": e["definition"], "page_number": e["page_number"]}
        for e in entries
    ], ensure_ascii=False)

    messages = [
        {"role": "system", "content": _CLOZE_PROMPT},
        {"role": "user", "content": f"Fachbegriffe:\n{glossary_info}\n\nTextkontext:\n{context}"},
    ]

    try:
        response = kisski._client.chat.completions.create(
            model=kisski._model, messages=messages, temperature=0.3,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        exercises = json.loads(answer)
        return {"exercises": exercises}
    except Exception as e:
        logger.error("Cloze generation error: {}", e)
        raise HTTPException(status_code=500, detail="Lückentext-Generierung fehlgeschlagen")


@router.post("/ki-tutor/modules/{module_uuid}/exercises/vocab-test")
@observe(name="ki-tutor-vocab-test")
async def generate_vocab_test(
    module_uuid: str,
    body: ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    _trace_kisski(kisski, "ki-tutor-vocab-test")
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

    glossary_info = json.dumps([
        {"id": e["id"], "term_de": e["term_de"], "term_en": e["term_en"],
         "definition": e["definition"], "page_number": e["page_number"]}
        for e in entries
    ], ensure_ascii=False)

    messages = [
        {"role": "system", "content": _VOCAB_TEST_PROMPT},
        {"role": "user", "content": f"Erstelle einen Vokabeltest zu diesen Fachbegriffen:\n{glossary_info}"},
    ]

    try:
        response = kisski._client.chat.completions.create(
            model=kisski._model, messages=messages, temperature=0.3,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        exercises = json.loads(answer)
        return {"exercises": exercises}
    except Exception as e:
        logger.error("Vocab test generation error: {}", e)
        raise HTTPException(status_code=500, detail="Vokabeltest-Generierung fehlgeschlagen")


# ─── Sprachtraining: Progress & Analytics ─────────────────────────────────────


@router.post("/ki-tutor/modules/{module_uuid}/vocab-progress")
async def record_progress(
    module_uuid: str,
    body: VocabProgressBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_ki_tutor_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    records = [
        {
            "glossary_entry_id": r["glossary_entry_id"],
            "user_id": user_id,
            "exercise_type": r["exercise_type"],
            "correct": r["correct"],
        }
        for r in body.results
    ]
    db.bulk_record_vocab_progress(records)
    return {"ok": True}


@router.get("/ki-tutor/modules/{module_uuid}/vocab-analytics")
async def get_analytics(
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

    return db.get_vocab_analytics_summary(module["id"], user_id)


# ─── Exercise Sets CRUD ──────────────────────────────────────────────────────

GLOSSARY_LIMIT = 150


class CreateSetBody(BaseModel):
    tool: str  # "lernkarten" | "lueckentext" | "vokabeltest"
    mode: str = "glossar"  # "glossar" | "quelle"
    source_uuid: Optional[str] = None
    count: int = 10


class ExerciseProgressBody(BaseModel):
    results: list[dict]  # [{"item_id": int, "correct": bool}]


def _generate_exercise_set_bg(set_id: int, module: dict, body_tool: str, body_mode: str, body_count: int, body_source_uuid: str | None, kisski_client):
    """Background task: generate items for an exercise set."""
    try:
        items = []
        title = "Wird generiert…"

        if body_mode == "glossar":
            glossary = db.get_ki_tutor_glossary_by_module(module["id"])
            if not glossary:
                db.fail_exercise_set(set_id)
                return
            import random
            selected = random.sample(glossary, min(body_count, len(glossary)))

            if body_tool == "lernkarten":
                items = [
                    {"front": e["term_de"], "back": f"{e['term_en']} — {e['definition']}",
                     "source_label": e.get("filename", ""), "page_number": e.get("page_number")}
                    for e in selected
                ]
                title = ", ".join(e["term_de"] for e in selected[:3]) + ("…" if len(selected) > 3 else "")
            elif body_tool == "lueckentext":
                terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
                messages = [
                    {"role": "system", "content": (
                        "Du erstellst Lückentext-Übungen. Für jeden Begriff erstelle einen Satz "
                        "mit einer Lücke, die durch den Begriff gefüllt werden muss.\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"sentence": "Der Prozess der ___ reduziert Redundanz.", '
                        '"answer": "Normalisierung", '
                        '"options": ["Indexierung", "Normalisierung", "Partitionierung", "Denormalisierung"], '
                        '"correct_idx": 1, "term_de": "Normalisierung", "page_number": 12}]\n\n'
                        "Regeln:\n- Genau 4 Optionen pro Frage, eine davon korrekt\n"
                        "- correct_idx = Index der richtigen Option (0-3)\n"
                        "- ___ als Lücken-Platzhalter\n- Antworte NUR mit dem JSON-Array"
                    )},
                    {"role": "user", "content": f"Erstelle Lückentext-Übungen:\n\n{terms_text}"},
                ]
                response = kisski_client._client.chat.completions.create(
                    model=kisski_client._model, messages=messages, temperature=0.3,
                    **(kisski_client._extra_body and {"extra_body": kisski_client._extra_body} or {}),
                )
                answer = response.choices[0].message.content.strip()
                if answer.startswith("```"): answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                exercises = json.loads(answer)
                items = [
                    {"front": ex["sentence"], "back": ex["answer"], "options": ex["options"],
                     "correct_idx": ex["correct_idx"],
                     "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == ex.get("term_de")), ""),
                     "page_number": ex.get("page_number")}
                    for ex in exercises
                ]
                title = ", ".join(e["term_de"] for e in selected[:3]) + ("…" if len(selected) > 3 else "")
            elif body_tool == "vokabeltest":
                terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
                messages = [
                    {"role": "system", "content": (
                        "Du erstellst Vokabeltest-Fragen (Multiple Choice).\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Was ist die englische Übersetzung von Normalisierung?", '
                        '"options": ["Indexing", "Normalization", "Partitioning", "Denormalization"], '
                        '"correct_idx": 1, "explanation": "Normalization ist...", '
                        '"term_de": "Normalisierung", "page_number": 12}]\n\n'
                        "Regeln:\n- Mische DE→EN, EN→DE, Definitionsfragen\n"
                        "- Genau 4 Optionen, eine korrekt\n- correct_idx = 0-3\n"
                        "- Antworte NUR mit dem JSON-Array"
                    )},
                    {"role": "user", "content": f"Erstelle Vokabeltest-Fragen:\n\n{terms_text}"},
                ]
                response = kisski_client._client.chat.completions.create(
                    model=kisski_client._model, messages=messages, temperature=0.3,
                    **(kisski_client._extra_body and {"extra_body": kisski_client._extra_body} or {}),
                )
                answer = response.choices[0].message.content.strip()
                if answer.startswith("```"): answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                questions = json.loads(answer)
                items = [
                    {"front": q["question"], "back": q["options"][q["correct_idx"]], "options": q["options"],
                     "correct_idx": q["correct_idx"], "explanation": q.get("explanation"),
                     "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == q.get("term_de")), ""),
                     "page_number": q.get("page_number")}
                    for q in questions
                ]
                title = ", ".join(e["term_de"] for e in selected[:3]) + ("…" if len(selected) > 3 else "")

        elif body_mode == "quelle":
            if not body_source_uuid:
                db.fail_exercise_set(set_id)
                return
            source = db.get_ki_tutor_source(body_source_uuid)
            if not source:
                db.fail_exercise_set(set_id)
                return
            source_label = source["filename"]
            summaries = db.get_paragraph_summaries_by_source(source["id"])
            if summaries:
                pages: dict[int, list[str]] = {}
                for s in summaries:
                    pages.setdefault(s["page_number"], []).append(s["summary"])
                parts = [f"[{source_label}, S. {p}] {' '.join(texts)}" for p, texts in sorted(pages.items())]
                context = "\n".join(parts)
            else:
                chunks = db.get_chunks_by_source(source["id"])
                if not chunks:
                    db.fail_exercise_set(set_id)
                    return
                parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks[:30]]
                context = "\n".join(parts)
            if len(context) > 16000:
                context = context[:16000]

            if body_tool == "lernkarten":
                prompt = TUTOR_LERNKARTEN_PROMPT.replace("{count}", str(body_count))
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Erstelle Lernkarten aus folgender Quelle:\n\n{context}"},
                ]
                response = kisski_client._client.chat.completions.create(
                    model=kisski_client._model, messages=messages, temperature=0.3,
                    **(kisski_client._extra_body and {"extra_body": kisski_client._extra_body} or {}),
                )
                answer = response.choices[0].message.content.strip()
                if answer.startswith("```"): answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                data = json.loads(answer)
                items = [
                    {"front": c["front"], "back": c["back"],
                     "source_label": c.get("source_label", source_label), "page_number": c.get("page_number")}
                    for c in data.get("cards", [])
                ]
                title = data.get("title", source_label)
            else:
                tool_prompt = "Du erstellst Übungen basierend auf dem gegebenen Quelltext.\n\n"
                if body_tool == "lueckentext":
                    tool_prompt += (
                        "Erstelle Lückentext-Übungen. Antworte NUR mit einem JSON-Array:\n"
                        '[{"sentence": "Satz mit ___ als Lücke", "answer": "Antwort", '
                        '"options": ["A", "B", "C", "D"], "correct_idx": 0, '
                        '"source_label": "Dateiname", "page_number": 5}]\n'
                        f"Erstelle genau {body_count} Übungen."
                    )
                else:
                    tool_prompt += (
                        "Erstelle Multiple-Choice Vokabeltest-Fragen. Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Frage?", "options": ["A", "B", "C", "D"], '
                        '"correct_idx": 0, "explanation": "Erklärung", '
                        '"source_label": "Dateiname", "page_number": 5}]\n'
                        f"Erstelle genau {body_count} Fragen."
                    )
                messages = [
                    {"role": "system", "content": tool_prompt},
                    {"role": "user", "content": f"Quelle:\n\n{context}"},
                ]
                response = kisski_client._client.chat.completions.create(
                    model=kisski_client._model, messages=messages, temperature=0.3,
                    **(kisski_client._extra_body and {"extra_body": kisski_client._extra_body} or {}),
                )
                answer = response.choices[0].message.content.strip()
                if answer.startswith("```"): answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                exercises = json.loads(answer)
                if body_tool == "lueckentext":
                    items = [
                        {"front": ex["sentence"], "back": ex["answer"], "options": ex["options"],
                         "correct_idx": ex["correct_idx"],
                         "source_label": ex.get("source_label", source_label), "page_number": ex.get("page_number")}
                        for ex in exercises
                    ]
                else:
                    items = [
                        {"front": q["question"], "back": q["options"][q["correct_idx"]], "options": q["options"],
                         "correct_idx": q["correct_idx"], "explanation": q.get("explanation"),
                         "source_label": q.get("source_label", source_label), "page_number": q.get("page_number")}
                        for q in exercises
                    ]
                title = source_label

        if not items:
            db.fail_exercise_set(set_id)
            return

        db.finalize_exercise_set(set_id, title, items)
    except Exception as e:
        logger.error("Background exercise set generation failed for set {}: {}", set_id, e)
        db.fail_exercise_set(set_id)


@router.post("/ki-tutor/modules/{module_uuid}/exercise-sets")
async def create_exercise_set(
    module_uuid: str,
    body: CreateSetBody,
    background_tasks: "BackgroundTasks" = None,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    """Create a new exercise set — returns immediately, generates in background."""
    from fastapi import BackgroundTasks as _BT
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

    # Create placeholder immediately
    placeholder = db.create_exercise_set_placeholder(
        module_id=module["id"], user_id=user_id, tool=body.tool,
        title="Wird generiert…", mode=body.mode, source_uuid=body.source_uuid,
    )

    # Run generation in background thread
    import threading
    thread = threading.Thread(
        target=_generate_exercise_set_bg,
        args=(placeholder["id"], module, body.tool, body.mode, body.count, body.source_uuid, kisski),
        daemon=True,
    )
    thread.start()

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
