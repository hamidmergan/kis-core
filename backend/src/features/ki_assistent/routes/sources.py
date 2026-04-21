"""KI-Assistent routes — sources upload, stream, convert."""

import io
import json
import re
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
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
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file, stream_s3_object
from src.tool_prompts import (
    KIA_SYSTEM_DIRECT,
    KIA_SYSTEM_DIRECT_WITH_CONTEXT,
    KIA_SYSTEM_RAG,
    KIA_POPUP_ACTIONS,
)

from src.features.ki_assistent.routes._helpers import (
    _trace_kisski,
    _convert_office_to_pdf,
    _mp4_faststart,
    _count_pages,
    _format_timestamp,
    _require_own_module,
    _save_source_file,
    _delete_source_files_for_module,
    _strip_image_text_layer,
    _markdown_fallback,
    _resolve_source_ids,
    _term_appears_in_text,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ki_assistent import schemas

router = APIRouter(tags=["ki-assistent"])

@router.post("/ki-assistent/modules/{module_uuid}/sources")
async def upload_source(
    module_uuid: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    module = _require_own_module(module_uuid, current_user["user_id"])

    existing_sources = db.get_kia_sources_by_module(module["id"])
    if len(existing_sources) >= KIA_MODULE_MAX_SOURCES:
        raise HTTPException(
            status_code=409,
            detail=f"Maximal {KIA_MODULE_MAX_SOURCES} Quellen pro Workspace erlaubt. Bitte lösche nicht mehr benötigte Quellen.",
        )

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

    stored_filename = file.filename
    if ext in (".docx", ".pptx"):
        logger.info("KI Tutor: converting {} to PDF ({})", ext, file.filename)
        data = _convert_office_to_pdf(data, ext)
        stored_filename = Path(file.filename).stem + ".pdf"
        ext = ".pdf"
    elif ext == ".mp4":
        logger.info("KI Tutor: applying MP4 faststart ({})", file.filename)
        data = _mp4_faststart(data)

    page_count = _count_pages(ext, data)
    if page_count is not None and page_count > KIA_SOURCE_MAX_PAGES:
        raise HTTPException(
            status_code=413,
            detail=f"Dokument hat {page_count} Seiten — max. {KIA_SOURCE_MAX_PAGES} Seiten erlaubt. Bitte teile das Dokument in kleinere Abschnitte auf.",
        )

    source_uuid = uuid.uuid4().hex
    username = current_user.get("username", "unknown")
    file_path = _save_source_file(username, module_uuid, source_uuid, ext, data)
    file_type = ext.lstrip(".")

    db.create_kia_source(
        module_id=module["id"],
        uuid=source_uuid,
        filename=stored_filename,
        file_path=file_path,
        file_type=file_type,
    )

    from src.tasks.kia_tasks import run_index_source
    run_index_source.delay(source_uuid)

    logger.info("KI Tutor: source {} ({}) uploaded to module {}", source_uuid, stored_filename, module_uuid)
    return {"uuid": source_uuid, "filename": stored_filename, "status": "pending"}

@router.post("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/retry")
async def retry_source(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    _require_own_module(module_uuid, current_user["user_id"])
    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")
    if source["status"] != "failed":
        raise HTTPException(status_code=409, detail="Nur fehlgeschlagene Quellen können neu indexiert werden")

    db.delete_kia_chunks_by_source(source["id"])
    db.reset_kia_source_for_retry(source_uuid)

    from src.tasks.kia_tasks import run_index_source
    run_index_source.delay(source_uuid)

    logger.info("KI Tutor: source {} retry dispatched", source_uuid)
    return {"uuid": source_uuid, "status": "pending"}

@router.delete("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}")
async def delete_source(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    _require_own_module(module_uuid, current_user["user_id"])
    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")
    try:
        delete_file(source["file_path"])
    except Exception as e:
        logger.warning("KI Tutor: could not delete source file {}: {}", source["file_path"], e)
    db.delete_kia_source(source_uuid)
    logger.info("KI Tutor: source {} deleted", source_uuid)
    return {"deleted": source_uuid}


# ─── Studenten-Endpunkte ──────────────────────────────────────────────────────

@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/file")
async def stream_source_file(
    module_uuid: str,
    source_uuid: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

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
    disposition = f'inline; filename="{source["filename"]}"'

    if USE_S3:
        # Stream durch das Backend statt Redirect zu presigned URL: gleiche
        # Origin wie die App, funktioniert damit auch vom Smartphone aus.
        range_header = request.headers.get("range")
        body_iter, content_length, content_range = stream_s3_object(source["file_path"], range_header)
        headers = {
            "Content-Disposition": disposition,
            "Cache-Control": "private, max-age=3600",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
        }
        if content_range:
            headers["Content-Range"] = content_range
        return StreamingResponse(
            body_iter,
            status_code=206 if range_header and content_range else 200,
            media_type=media_type,
            headers=headers,
        )

    return FileResponse(
        path=source["file_path"],
        media_type=media_type,
        filename=source["filename"],
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )

@router.post("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/regenerate-en-transcript")
async def regenerate_en_transcript(
    module_uuid: str,
    source_uuid: str,
    provider: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Dispatch an async Celery task to translate the source-language VTT to English.

    If ``provider`` is omitted, falls back to the admin-configured default
    (``transcript_translation_provider`` setting; defaults to ``llm``).
    """
    _require_own_module(module_uuid, current_user["user_id"])
    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    effective_provider = provider or db.get_setting("transcript_translation_provider", "llm")
    if effective_provider not in ("deepl", "llm"):
        raise HTTPException(status_code=400, detail="Ungültiger Provider")

    base_key = source["file_path"].rsplit(".", 1)[0]
    if not any(file_exists(f"{base_key}_transcript.{lang}.vtt") for lang in ("de",)):
        raise HTTPException(
            status_code=404,
            detail="Kein Quell-Transkript gefunden. Neu-Übersetzung nicht möglich.",
        )

    from src.tasks.kia_tasks import run_translate_transcript_en
    run_translate_transcript_en.delay(source_uuid, effective_provider)
    logger.info(
        "KI Tutor: manual EN translation dispatched for {} (provider={})",
        source_uuid, effective_provider,
    )
    return {"uuid": source_uuid, "status": "dispatched", "provider": effective_provider}


@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/transcript")
async def get_transcript_vtt(
    module_uuid: str,
    source_uuid: str,
    lang: str,
    current_user: dict = Depends(get_current_user),
):
    """Return a WebVTT transcript for a media source in the requested language."""
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    # Only allow lowercase ISO-like language codes (2-5 chars)
    lang_clean = (lang or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2,5}", lang_clean):
        raise HTTPException(status_code=400, detail="Ungültiger Sprachcode")

    base_key = source["file_path"].rsplit(".", 1)[0]
    vtt_key = f"{base_key}_transcript.{lang_clean}.vtt"
    if not file_exists(vtt_key):
        raise HTTPException(status_code=404, detail="Transkript nicht verfügbar")

    data = get_file(vtt_key)
    return Response(
        content=data,
        media_type="text/vtt; charset=utf-8",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/toc")
async def get_pdf_toc(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Liefert das gespeicherte Inhaltsverzeichnis aus der DB."""
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    return {"toc": source.get("toc") or []}

@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/summaries")
async def get_paragraph_summaries(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Return page-level summaries for the sidebar."""
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
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

@router.post("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/summaries/generate")
async def trigger_paragraph_summaries(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger paragraph summary generation for a source."""
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    if module["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")
    if source["file_type"] != "pdf":
        raise HTTPException(status_code=400, detail="Nur für PDF-Dateien verfügbar")

    status = source.get("summaries_status", "none")
    if status == "generating":
        return {"status": "generating"}

    # Keep existing summaries — task resumes where it left off
    db.update_kia_source_summaries_status(source_uuid, "generating")

    from src.tasks.kia_tasks import run_generate_summaries
    run_generate_summaries.delay(source_uuid)
    return {"status": "generating"}

@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/search")
async def search_pdf(
    module_uuid: str,
    source_uuid: str,
    q: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
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

@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/markdown")
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
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
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

    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=md_path, Body=markdown.encode("utf-8"))
    else:
        Path(md_path).write_text(markdown, encoding="utf-8")

    return {"markdown": markdown}

