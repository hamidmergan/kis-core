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

_LANG_LABELS = {
    "DE": "Deutsch",
    "EN-US": "Englisch",
    "EN-GB": "Englisch (UK)",
    "FR": "Französisch",
    "ES": "Spanisch",
    "IT": "Italienisch",
}


@router.get("/translate/config")
async def get_translate_config(current_user: dict = Depends(get_current_user)):
    settings = get_settings()

    from src.dependencies import _resolve_llm_provider
    _, _, _llm_model, _ = _resolve_llm_provider()
    providers = [
        {"id": "deepl", "label": "DeepL Übersetzer (schnell)"},
    ]
    if is_admin_user(current_user):
        providers.append({"id": "llm", "label": f"LLM {_llm_model} (langsam, experimentell)"})

    raw_langs = [lang.strip() for lang in settings.translation_languages.split(",") if lang.strip()]
    languages = [{"id": lang, "label": _LANG_LABELS.get(lang, lang)} for lang in raw_langs]

    return {
        "providers": providers,
        "default_provider": "deepl",
        "languages": languages,
        "default_source": "DE",
        "default_target": "EN-US",
    }


def translate_pptx_content(
    content: bytes,
    filename: str,
    glossary_json: str = "",
    source_lang: str = "",
    target_lang: str = "",
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
        eff_source = source_lang if source_lang else "DE"
        eff_target = target_lang if target_lang else "EN-US"
        return translate_pptx(content, eff_source, eff_target, service)
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
    translation_provider: str = Form(""),
    source_lang: str = Form(""),
    target_lang: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    if translation_provider == "llm" and not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="LLM-Provider ist nur für Admins verfügbar")

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

    effective_source = source_lang or ""
    effective_target = target_lang or "EN-US"

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_quota(user_id, "translate", is_admin_user(current_user))

    db.create_job(job_uuid, user_id, "translation", file.filename, username=current_user.get("username", "unknown"))
    input_path = save_queue_file(job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_translate
    run_translate.delay(
        job_uuid,
        input_path,
        file.filename,
        glossary,
        effective_source,
        effective_target,
        translation_provider,
    )

    logger.info("Translate job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
