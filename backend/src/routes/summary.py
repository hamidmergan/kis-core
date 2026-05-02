"""Summary route: generate a text summary from various file formats via KISSKI LLM."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.storage import save_queue_file
from src.utils.file_validation import (
    MAX_UPLOAD_BYTES,
    SUMMARY_EXTENSIONS,
    SUMMARY_MAX_CHARS,
    validate_or_raise,
)
from src.utils.text_extraction import EXTRACTORS

router = APIRouter(tags=["summary"])

_OUTPUT_MIME = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
}


@router.post("/summary")
async def summarize(
    request: Request,
    file: UploadFile = File(...),
    output_format: str = Form("txt"),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Generate a summary of the uploaded file using KISSKI LLM."""
    if not file.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))

    ext = Path(file.filename).suffix.lower()
    if ext not in SUMMARY_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=t(
                "summary.unsupportedFormat",
                locale,
                formats=", ".join(sorted(SUMMARY_EXTENSIONS)),
            ),
        )

    if output_format not in _OUTPUT_MIME:
        raise HTTPException(
            status_code=400,
            detail=t("summary.invalidOutputFormat", locale),
        )

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb500", locale))

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=t("file.empty", locale))
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=t("summary.fileTooLarge", locale))
    validate_or_raise(content, ext, locale)

    extractor = EXTRACTORS.get(ext)
    if extractor is not None:
        text = extractor(content)
        if len(text) > SUMMARY_MAX_CHARS:
            raise HTTPException(
                status_code=422,
                detail=t(
                    "summary.documentTooLong",
                    locale,
                    chars=f"{len(text):,}".replace(",", "."),
                    maxChars=f"{SUMMARY_MAX_CHARS:,}".replace(",", "."),
                ),
            )

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_tool_burst(user_id, "summary", locale)
    enforce_quota(user_id, "summary", is_admin_user(current_user), locale)

    db.create_job(job_uuid, user_id, "summary", file.filename, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_summary
    run_summary.delay(job_uuid, input_path, file.filename, output_format)

    logger.info("Summary job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
