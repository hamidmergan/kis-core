"""Summary route: generate a text summary from various file formats via the admin-configured LLM."""

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.services import feature_provider_choices
from src.storage import save_queue_file_from_path
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import (
    SUMMARY_EXTENSIONS,
    SUMMARY_MAX_CHARS,
    validate_or_raise,
)
from src.utils.text_extraction import EXTRACTORS
from src.utils.upload_stream import stream_upload_to_path
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    tags=["summary"],
    dependencies=[Depends(require_tool_access("summary"))],
)


@router.get("/summary/providers")
async def list_summary_providers(_user: dict = Depends(get_current_user)):
    """Reachable chat-capable providers the admin configured a model for. The
    summary tool runs on the chat LLM, so the picker mirrors the chat route."""
    return await feature_provider_choices.list_reachable_choices("chat")


@router.post("/summary")
async def summarize(
    request: Request,
    file: UploadFile = File(...),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Generate a summary of the uploaded file using the admin-configured LLM."""
    if not file.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))

    # A user-picked provider must be one the admin configured a chat model for.
    # Omitting provider_id keeps the admin default chat route.
    if provider_id is not None and not feature_provider_choices.is_eligible("chat", provider_id):
        raise HTTPException(status_code=400, detail=t("summary.invalidProvider", locale))

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

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > max_upload_bytes():
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb", locale, max=max_upload_bytes() // (1024 * 1024)))

    # Stream to a temp file instead of holding the body (up to 500 MB) in RAM.
    # The extractor reads the path, storage uploads from the path.
    with tempfile.TemporaryDirectory(prefix="summary_upload_") as tmpdir:
        tmp_path = os.path.join(tmpdir, f"input{ext}")
        total, head = await stream_upload_to_path(file, tmp_path, max_upload_bytes(), locale)
        if not total:
            raise HTTPException(status_code=400, detail=t("file.empty", locale))
        validate_or_raise(head, ext, locale)

        extractor = EXTRACTORS.get(ext)
        if extractor is not None:
            text = extractor(tmp_path)
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
        input_path = save_queue_file_from_path(user_id, job_uuid, ext, tmp_path)
        db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_summary
    run_summary.delay(job_uuid, input_path, file.filename, provider_id)

    logger.info("Summary job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
