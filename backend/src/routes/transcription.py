"""Transcription route: audio/video file to text, SRT, or VTT."""

import asyncio
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
from src.services.job_lanes import media_seconds, transcribe_route
from src.services.open_jobs import enforce_open_jobs
from src.services import feature_provider_choices
from src.storage import save_queue_file_from_path
from src.utils.file_validation import TRANSCRIPTION_EXTENSIONS, validate_or_raise
from src.services.tool_limits import max_upload_bytes
from src.utils.upload_stream import stream_upload_to_path
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    tags=["transcription"],
    dependencies=[Depends(require_tool_access("transcription"))],
)



_VALID_TASKS = {"transcribe"}
_VALID_FORMATS = {"text", "srt", "vtt"}


@router.get("/transcription/providers")
async def list_transcription_providers(current_user: dict = Depends(get_current_user)):
    """Reachable speech recognition providers, empty means the choice stays hidden."""
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

    # A chosen provider must be set up by the admin.
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
    if content_length is not None and int(content_length) > max_upload_bytes():
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb", locale, max=max_upload_bytes() // (1024 * 1024)))

    # Stream to a temp file, media quickly reach hundreds of MB.
    with tempfile.TemporaryDirectory(prefix="stt_upload_") as tmpdir:
        tmp_path = os.path.join(tmpdir, f"input{ext}")
        total, head = await stream_upload_to_path(file, tmp_path, max_upload_bytes(), locale)
        if not total:
            raise HTTPException(status_code=400, detail=t("file.empty", locale))
        validate_or_raise(head, ext, locale)
        sekunden = await asyncio.to_thread(media_seconds, tmp_path)

        job_uuid = uuid.uuid4().hex
        user_id = current_user.get("user_id", 0)
        enforce_open_jobs(user_id, locale)
        enforce_tool_burst(user_id, "transcription", locale)
        enforce_quota(user_id, "transcription", is_admin_user(current_user), locale)

        db.create_job(job_uuid, user_id, "transcription", file.filename, locale=locale)
        input_path = await asyncio.to_thread(save_queue_file_from_path, user_id, job_uuid, ext, tmp_path)
        db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_transcribe
    celery_task = run_transcribe.apply_async(
        args=[job_uuid, input_path, file.filename, task, response_format, provider_id],
        **transcribe_route(sekunden),
    )
    db.set_job_celery_task_id(job_uuid, celery_task.id)

    logger.info("Transcribe job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
