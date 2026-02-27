import json
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, get_deepl_client, get_settings
from src.services.glossary import GlossaryService
from src.services.translation import TranslationService
from src.storage import save_result_file
from src.translators.docx import translate_docx
from src.translators.pptx import translate_pptx
from src.translators.markdown import translate_markdown_preserve_code_blocks
from src.translators.latex import translate_latex_preserve_structure
from src.utils.file_validation import (
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_BYTES,
)

router = APIRouter(tags=["translate"])


def _build_service(glossary_json: str = "") -> TranslationService:
    """Create a per-request TranslationService with optional glossary entries."""
    client = get_deepl_client()
    if client is None:
        raise HTTPException(
            status_code=500,
            detail="DeepL API Key fehlt oder Translator konnte nicht initialisiert werden",
        )
    glossary = GlossaryService()
    if glossary_json:
        try:
            entries = json.loads(glossary_json)
            if isinstance(entries, dict):
                glossary.set_entries(entries)
        except (json.JSONDecodeError, TypeError):
            pass
    return TranslationService(deepl_client=client, glossary=glossary)


def translate_pptx_content(
    content: bytes,
    filename: str,
    glossary_json: str = "",
) -> bytes:
    service = _build_service(glossary_json)
    settings = get_settings()
    try:
        return translate_pptx(content, settings.source_lang, settings.effective_target_lang, service)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"PPTX-Übersetzungsfehler: {str(e)}")
    except Exception as e:
        logger.exception("PPTX processing error for file '{}'", filename)
        raise HTTPException(status_code=500, detail=f"PPTX-Verarbeitungsfehler: {str(e)}")


@router.post("/translate")
async def translate(
    request: Request,
    file: UploadFile = File(...),
    glossary: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Nur .docx, .pptx, .md oder .tex erlaubt")

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    settings = get_settings()
    target_lang = settings.effective_target_lang
    source_lang = settings.source_lang
    service = _build_service(glossary)

    translated_filename = service.translate_filename(file.filename, source_lang, target_lang)
    download_name = translated_filename

    if ext == ".md":
        try:
            text = content.decode("utf-8")
            translated_text = translate_markdown_preserve_code_blocks(
                text, source_lang, target_lang, service
            )
            content = translated_text.encode("utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"uebersetzungsfehler: {str(e)}")
    elif ext == ".tex":
        try:
            text = content.decode("utf-8")
            translated_text = translate_latex_preserve_structure(
                text, source_lang, target_lang, service
            )
            content = translated_text.encode("utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"LaTeX-Übersetzungsfehler: {str(e)}"
            )
    elif ext == ".docx":
        try:
            content = translate_docx(content, source_lang, target_lang, service)
        except ValueError as e:
            raise HTTPException(
                status_code=500, detail=f"DOCX-Übersetzungsfehler: {str(e)}"
            )
        except Exception as e:
            logger.exception("DOCX processing error for file '{}'", file.filename)
            raise HTTPException(
                status_code=500, detail=f"DOCX-Verarbeitungsfehler: {str(e)}"
            )
    elif ext == ".pptx":
        content = translate_pptx_content(content, file.filename, glossary)
    else:
        raise HTTPException(status_code=400, detail="Dateityp wird nicht unterstützt")

    logger.info("Translation completed: '{}' -> '{}'", file.filename, download_name)

    # Save result to job history (non-fatal if storage fails)
    try:
        job_uuid = uuid.uuid4().hex
        user_id = current_user.get("user_id", 0)
        result_path = save_result_file(job_uuid, ext, content)
        db.create_job(job_uuid, user_id, "translation", file.filename)
        db.update_job_result(job_uuid, result_path, download_name)
        db.update_job_status(job_uuid, "success")
    except Exception:
        logger.exception("Job tracking failed for translation of '{}'", file.filename)

    encoded_filename = quote(download_name, safe="")
    return StreamingResponse(
        iter([content]),
        media_type=ALLOWED_EXTENSIONS[ext],
        headers={
            "Content-Disposition": f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        },
    )
