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
from src.storage import USE_S3, delete_file, get_file, save_file

router = APIRouter(tags=["ki-tutor"])

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


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

    if body.direct_text:
        # Kein RAG — direkt den Text bearbeiten (für Popup-Aktionen wie Kürzen, Umformulieren etc.)
        chunks = []
        system_prompt = "Du bist ein hilfreicher Assistent. Führe die Aufgabe präzise aus."
        user_message = body.question
    else:
        # Embed question
        from src.services.ki_tutor_embeddings import get_embedding_provider
        provider = get_embedding_provider()
        query_vector = provider.embed_one(body.question)

        # Search similar chunks
        chunks = db.search_similar_chunks(module["id"], query_vector, source_ids=source_ids, limit=5)

        # Build context (max 4000 chars)
        context_parts: list[str] = []
        context_len = 0
        for chunk in chunks:
            part = chunk["content"]
            if context_len + len(part) > 4000:
                break
            context_parts.append(part)
            context_len += len(part)
        context = "\n\n---\n\n".join(context_parts)

        system_prompt = (
            "Du bist ein KI-Tutor. Antworte ausschließlich auf Basis der gegebenen Quellen. "
            "Nenne immer die Seitenzahl. Halluziniere nicht."
        )
        user_message = f"Frage: {body.question}\n\nQuellen:\n{context}"

    try:
        response = kisski._client.chat.completions.create(
            model=kisski._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content or ""
        answer = answer.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM-Fehler: {e}") from e

    # Build source_pages from returned chunks
    all_sources = {s["id"]: s for s in db.get_ki_tutor_sources_by_module(module["id"])}
    source_pages: list[dict] = []
    seen: set[tuple] = set()
    for chunk in chunks:
        source = all_sources.get(chunk["source_id"])
        if source:
            key = (source["uuid"], chunk["page_number"])
            if key not in seen:
                seen.add(key)
                source_pages.append({
                    "source_uuid": source["uuid"],
                    "filename": source["filename"],
                    "page_number": chunk["page_number"],
                })
    source_pages.sort(key=lambda x: x["page_number"])

    # Save messages
    db.save_ki_tutor_message(module["id"], user_id, "user", body.question)
    db.save_ki_tutor_message(module["id"], user_id, "assistant", answer, source_pages=source_pages)

    return {"answer": answer, "source_pages": source_pages}


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
