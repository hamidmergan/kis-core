"""Transcription route: audio/video file to text, SRT, or VTT."""

import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_current_user, get_kisski_client
from src.storage import save_result_file
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
_FORMAT_EXT = {"text": ".txt", "srt": ".srt", "vtt": ".vtt"}
_FORMAT_MIME = {
    "text": "text/plain",
    "srt": "application/x-subrip",
    "vtt": "text/vtt",
}



@router.post("/transcription")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
    task: str = Form("transcribe"),
    response_format: str = Form("text"),
    current_user: dict = Depends(get_current_user),
):
    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    ext = Path(file.filename).suffix.lower()
    if ext not in TRANSCRIPTION_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(TRANSCRIPTION_EXTENSIONS.keys())} allowed",
        )

    # Validate parameters
    if task not in _VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Invalid task: {task}")
    if response_format not in _VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format: {response_format}")

    # Validate file size
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 500 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(content) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 500 MB)")

    client = get_kisski_client()
    stem = Path(file.filename).stem

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / f"input{ext}"
        input_file.write_bytes(content)

        logger.info("Transcription started: file='{}', task='{}', format='{}'", file.filename, task, response_format)

        try:
            if task == "translate":
                result_text = client.transcribe_and_translate(str(input_file), response_format=response_format)
            else:
                result_text = client.transcribe(str(input_file), response_format=response_format)
        except RuntimeError as e:
            logger.error("Transcription failed for '{}': {}", file.filename, e)
            raise HTTPException(status_code=502, detail=str(e))

    logger.info("Transcription complete: file='{}', output_length={}", file.filename, len(result_text))

    out_ext = _FORMAT_EXT[response_format]
    suffix = "_EN" if task == "translate" else ""
    output_name = f"{Path(file.filename).stem}{suffix}{out_ext}"

    # Save result to job history (non-fatal if storage fails)
    try:
        job_uuid = uuid.uuid4().hex
        user_id = current_user.get("user_id", 0)
        result_path = save_result_file(job_uuid, out_ext, result_text.encode("utf-8"))
        db.create_job(job_uuid, user_id, "transcription", file.filename)
        db.update_job_result(job_uuid, result_path, output_name)
        db.update_job_status(job_uuid, "success")
    except Exception:
        logger.exception("Job tracking failed for transcription of '{}'", file.filename)

    mime = _FORMAT_MIME[response_format]

    return StreamingResponse(
        iter([result_text.encode("utf-8")]),
        media_type=mime,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{encoded_name}"; '
                f"filename*=UTF-8''{encoded_name}"
            )
        },
    )
