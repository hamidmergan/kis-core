import os
import tempfile
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
from src.storage import save_queue_file_from_path
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import (
    ALLOWED_EXTENSIONS,
    TRANSLATE_MAX_CHARS,
    validate_or_raise,
)
from src.utils.text_extraction import EXTRACTORS
from src.utils.upload_stream import stream_upload_to_path
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
    if content_length is not None and int(content_length) > max_upload_bytes():
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb", locale, max=max_upload_bytes() // (1024 * 1024)))

    # Stream to a temp file instead of holding the body (up to 500 MB) in RAM.
    # The extractor reads the path, storage uploads from the path.
    with tempfile.TemporaryDirectory(prefix="translate_upload_") as tmpdir:
        tmp_path = os.path.join(tmpdir, f"input{ext}")
        total, head = await stream_upload_to_path(file, tmp_path, max_upload_bytes(), locale)
        if not total:
            raise HTTPException(status_code=400, detail=t("file.empty", locale))
        validate_or_raise(head, ext, locale)

        extractor = EXTRACTORS.get(ext)
        if extractor is not None:
            text = extractor(tmp_path)
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
        input_path = save_queue_file_from_path(user_id, job_uuid, ext, tmp_path)
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
