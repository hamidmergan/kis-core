"""Transcription route: audio/video file to text, SRT, or VTT."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_current_user, get_kisski_client, is_admin_user
from src.quotas import enforce_quota
from src.storage import save_queue_file
from src.utils.file_validation import MAX_TRANSCRIPTION_BYTES, TRANSCRIPTION_EXTENSIONS

router = APIRouter(tags=["transcription"])


class SummarizeRequest(BaseModel):
    text: str
    task: str = "transcribe"


@router.post("/transcription/summarize")
async def summarize_transcript(body: SummarizeRequest):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text darf nicht leer sein")
    if body.task not in {"transcribe", "translate"}:
        raise HTTPException(status_code=400, detail="Ungültige Aufgabe")

    client = get_kisski_client()
    try:
        summary = client.summarize(body.text, task=body.task)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    logger.info("Summarization completed: task='{}', {} chars → {} chars", body.task, len(body.text), len(summary))
    return {"summary": summary}


_VALID_TASKS = {"transcribe", "translate"}
_VALID_FORMATS = {"text", "srt", "vtt"}


@router.post("/transcription")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    task: str = Form("transcribe"),
    response_format: str = Form("text"),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    ext = Path(file.filename).suffix.lower()
    if ext not in TRANSCRIPTION_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(TRANSCRIPTION_EXTENSIONS.keys())} allowed",
        )

    if task not in _VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Invalid task: {task}")
    if response_format not in _VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format: {response_format}")

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 500 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(content) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 500 MB)")

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_quota(user_id, "transcription", is_admin_user(current_user))

    db.create_job(job_uuid, user_id, "transcription", file.filename)
    input_path = save_queue_file(job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_transcribe
    run_transcribe.delay(job_uuid, input_path, file.filename, task, response_format)

    logger.info("Transcribe job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
