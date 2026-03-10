import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, get_settings, is_admin_user
from src.quotas import enforce_quota
from src.storage import save_queue_file
from src.utils.file_validation import (
    ALLOWED_EXTENSIONS,
    TRANSLATE_MAX_UPLOAD_BYTES,
    TRANSLATE_MAX_CHARS,
)
from src.utils.text_extraction import EXTRACTORS

router = APIRouter(tags=["translate"])


def translate_pptx_content(
    content: bytes,
    filename: str,
    glossary_json: str = "",
) -> bytes:
    """Synchronous PPTX translation helper — used by screencast.py."""
    import json
    from src.services.deepl_client import DeepLClient
    from src.services.glossary import GlossaryService
    from src.services.translation import TranslationService
    from src.translators.pptx import translate_pptx

    settings = get_settings()
    api_key = settings.deepl_api_key
    if not api_key:
        raise HTTPException(status_code=500, detail="DeepL API Key fehlt")
    deepl_client = DeepLClient(api_key)
    glossary = GlossaryService()
    if glossary_json:
        try:
            entries = json.loads(glossary_json)
            if isinstance(entries, dict):
                glossary.set_entries(entries)
        except (json.JSONDecodeError, TypeError):
            pass
    service = TranslationService(deepl_client=deepl_client, glossary=glossary)
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
        raise HTTPException(status_code=400, detail="Nur .docx, .pptx, .md, .tex oder .txt erlaubt")

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > TRANSLATE_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 500 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(content) > TRANSLATE_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 500 MB)")

    extractor = EXTRACTORS.get(ext)
    if extractor is not None:
        text = extractor(content)
        if len(text) > TRANSLATE_MAX_CHARS:
            raise HTTPException(
                status_code=422,
                detail=f"Dokument zu lang ({len(text):,} Zeichen). Bitte aufteilen (max. {TRANSLATE_MAX_CHARS:,} Zeichen).".replace(",", "."),
            )

    settings = get_settings()
    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_quota(user_id, "translate", is_admin_user(current_user))

    db.create_job(job_uuid, user_id, "translation", file.filename)
    input_path = save_queue_file(job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_translate
    run_translate.delay(
        job_uuid,
        input_path,
        file.filename,
        glossary,
        settings.source_lang,
        settings.effective_target_lang,
    )

    logger.info("Translate job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
