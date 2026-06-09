"""Transcription route: audio/video file to text, SRT, or VTT."""

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
from src.storage import save_queue_file
from src.utils.file_validation import MAX_TRANSCRIPTION_BYTES, TRANSCRIPTION_EXTENSIONS, validate_or_raise
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    tags=["transcription"],
    dependencies=[Depends(require_tool_access("transcription"))],
)



_VALID_TASKS = {"transcribe"}
_VALID_FORMATS = {"text", "srt", "vtt"}


@router.get("/transcription/providers")
async def list_transcription_providers(current_user: dict = Depends(get_current_user)):
    """STT providers the admin configured a model for, filtered to those
    currently reachable. Mirrors the TTS tool's provider picker.

    Returns an empty list when nothing is configured/reachable — the tool then
    hides the dropdown and falls back to the admin default route.
    """
    return await feature_provider_choices.list_reachable_choices("stt")


@router.post("/transcription")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    task: str = Form("transcribe"),
    response_format: str = Form("text"),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))

    # When the user picked a provider, it must be one the admin configured a
    # model for. Reject anything else so a forged id can't bypass the route.
    # Omitting provider_id keeps the admin default route.
    if provider_id is not None and not feature_provider_choices.is_eligible("stt", provider_id):
        raise HTTPException(status_code=400, detail=t("transcription.invalidProvider", locale))

    ext = Path(file.filename).suffix.lower()
    if ext not in TRANSCRIPTION_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=t(
                "transcription.unsupportedFormat",
                locale,
                formats=", ".join(TRANSCRIPTION_EXTENSIONS.keys()),
            ),
        )

    if task not in _VALID_TASKS:
        raise HTTPException(status_code=400, detail=t("transcription.invalidTask", locale, task=task))
    if response_format not in _VALID_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=t("transcription.invalidFormat", locale, format=response_format),
        )

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb500", locale))

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=t("file.empty", locale))
    if len(content) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb500", locale))
    validate_or_raise(content, ext, locale)

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_tool_burst(user_id, "transcription", locale)
    enforce_quota(user_id, "transcription", is_admin_user(current_user), locale)

    db.create_job(job_uuid, user_id, "transcription", file.filename, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_transcribe
    run_transcribe.delay(job_uuid, input_path, file.filename, task, response_format, provider_id)

    logger.info("Transcribe job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
