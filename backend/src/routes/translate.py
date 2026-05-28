import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import (
    DEFAULT_TRANSLATE_SOURCE,
    DEFAULT_TRANSLATE_TARGET,
    TRANSLATE_LANGUAGES,
    get_locale,
    t,
)
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.storage import save_queue_file
from src.utils.file_validation import (
    ALLOWED_EXTENSIONS,
    TRANSLATE_MAX_UPLOAD_BYTES,
    TRANSLATE_MAX_CHARS,
    validate_or_raise,
)
from src.utils.text_extraction import EXTRACTORS
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    tags=["translate"],
    dependencies=[Depends(require_tool_access("translation"))],
)

@router.get("/translate/config")
async def get_translate_config(
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    from src.dependencies import get_translation_providers
    raw_providers = get_translation_providers()
    providers = [{"id": p["id"], "label": p["name"]} for p in raw_providers]

    languages = [{"id": lang, "label": t(f"lang.{lang}", locale)} for lang in TRANSLATE_LANGUAGES]

    return {
        "providers": providers,
        "languages": languages,
        "default_source": DEFAULT_TRANSLATE_SOURCE,
        "default_target": DEFAULT_TRANSLATE_TARGET,
    }


def translate_pptx_content(
    content: bytes,
    filename: str,
    glossary_json: str = "",
    source_lang: str = "",
    target_lang: str = "",
    locale: str = "de",
) -> bytes:
    """Synchronous PPTX translation helper - used by screencast.py."""
    import json
    from src.services.deepl_client import DeepLClient
    from src.services.glossary import GlossaryService
    from src.services.translation import TranslationService
    from src.translators.pptx import translate_pptx

    from src.dependencies import resolve_deepl_api_key
    api_key = resolve_deepl_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail=t("translate.deeplKeyMissing", locale))
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
        eff_source = source_lang if source_lang else DEFAULT_TRANSLATE_SOURCE
        eff_target = target_lang if target_lang else DEFAULT_TRANSLATE_TARGET
        return translate_pptx(content, eff_source, eff_target, service)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=t("translate.pptxError", locale, error=str(e)))
    except Exception as e:
        logger.exception("PPTX processing error for file '{}'", filename)
        raise HTTPException(status_code=500, detail=t("translate.pptxProcessingError", locale, error=str(e)))


@router.post("/translate")
async def translate(
    request: Request,
    file: UploadFile = File(...),
    glossary: str = Form(""),
    provider_id: int | None = Form(None),
    source_lang: str = Form(""),
    target_lang: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=t("translate.unsupportedFormat", locale))

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > TRANSLATE_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb500", locale))

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=t("file.empty", locale))
    if len(content) > TRANSLATE_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb500", locale))
    validate_or_raise(content, ext, locale)

    extractor = EXTRACTORS.get(ext)
    if extractor is not None:
        text = extractor(content)
        if len(text) > TRANSLATE_MAX_CHARS:
            raise HTTPException(
                status_code=422,
                detail=t(
                    "translate.documentTooLong",
                    locale,
                    chars=f"{len(text):,}".replace(",", "."),
                    maxChars=f"{TRANSLATE_MAX_CHARS:,}".replace(",", "."),
                ),
            )

    effective_source = source_lang or ""
    effective_target = target_lang or DEFAULT_TRANSLATE_TARGET

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_tool_burst(user_id, "translate", locale)
    enforce_quota(user_id, "translate", is_admin_user(current_user), locale)

    db.create_job(job_uuid, user_id, "translation", file.filename, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_translate
    run_translate.delay(
        job_uuid,
        input_path,
        file.filename,
        glossary,
        effective_source,
        effective_target,
        provider_id,
    )

    logger.info("Translate job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
