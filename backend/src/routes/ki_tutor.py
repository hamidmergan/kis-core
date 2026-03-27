"""KI Tutor routes – Dozenten- und Studenten-Endpunkte."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_current_user, get_kisski_client
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
from src.tool_prompts import TUTOR_SYSTEM_DIRECT, TUTOR_SYSTEM_DIRECT_WITH_CONTEXT, TUTOR_SYSTEM_RAG, TUTOR_POPUP_ACTIONS

router = APIRouter(tags=["ki-tutor"])

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
    sprachtraining_active: bool


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
async def chat(
    module_uuid: str,
    body: ChatBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
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

    try:
        response = kisski._client.chat.completions.create(
            model=kisski._model,
            messages=messages,
            temperature=0.2,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content or ""
        answer = answer.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM-Fehler: {e}") from e

    # Build source_pages
    source_pages: list[dict] = []

    if body.source_text and body.source_uuid and body.source_page:
        # Popup-Aktion: eine Quelle mit markiertem Text für Highlight bei Klick
        source_pages.append({
            "source_uuid": body.source_uuid,
            "filename": body.source_filename or "",
            "page_number": body.source_page,
            "source_text": body.source_text,
        })
        # Klickbare Referenz an Antwort anhängen
        answer += f" [S. {body.source_page}]"
    else:
        # Normaler Chat: Quellen aus RAG-Chunks (mit Textsnippet für Highlight)
        all_sources = {s["id"]: s for s in db.get_ki_tutor_sources_by_module(module["id"])}
        seen: set[tuple] = set()
        for chunk in chunks:
            source = all_sources.get(chunk["source_id"])
            if source:
                key = (source["uuid"], chunk["page_number"])
                if key not in seen:
                    seen.add(key)
                    # First ~120 chars of chunk as highlight text for pill navigation
                    snippet = (chunk.get("content") or "")[:120].strip()
                    source_pages.append({
                        "source_uuid": source["uuid"],
                        "filename": source["filename"],
                        "page_number": chunk["page_number"],
                        "source_text": snippet,
                    })
        source_pages.sort(key=lambda x: x["page_number"])

    # Save messages
    db.save_ki_tutor_message(module["id"], user_id, "user", body.question)
    db.save_ki_tutor_message(module["id"], user_id, "assistant", answer, source_pages=source_pages)

    return {"answer": answer, "source_pages": source_pages, "source_qmap": source_qmap}


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
        module["id"], user_id, body.chat_lang, body.sprachtraining_active
    )
    return {"ok": True}
