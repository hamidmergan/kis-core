"""Summary route: generate a text summary from various file formats via KISSKI LLM."""

import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, get_kisski_client
from src.storage import save_result_file
from src.utils.file_validation import (
    MAX_TRANSCRIPTION_BYTES,
    MAX_UPLOAD_BYTES,
    SUMMARY_EXTENSIONS,
)
from src.utils.text_extraction import EXTRACTORS

router = APIRouter(tags=["summary"])

_MIN_WORDS = 20
_CONTEXT_WARN_CHARS = 80_000  # ~20k tokens

_OUTPUT_MIME = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
}
_OUTPUT_EXT = {"txt": ".txt", "md": ".md", "html": ".html"}


@router.post("/summary")
async def summarize(
    request: Request,
    file: UploadFile = File(...),
    user_prompt: str = Form(""),
    output_format: str = Form("md"),
    current_user: dict = Depends(get_current_user),
):
    """Generate a summary of the uploaded file using KISSKI LLM."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUMMARY_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Nur {', '.join(sorted(SUMMARY_EXTENSIONS))} erlaubt",
        )

    if output_format not in _OUTPUT_MIME:
        raise HTTPException(
            status_code=400,
            detail="output_format muss 'txt', 'md' oder 'html' sein",
        )

    is_audio = ext == ".mp3"
    max_bytes = MAX_TRANSCRIPTION_BYTES if is_audio else MAX_UPLOAD_BYTES
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > max_bytes:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 500 MB für Audio, 200 MB sonst)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Datei zu groß")

    client = get_kisski_client()

    # ── Text extraction ───────────────────────────────────────────────────────
    if is_audio:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / f"input{ext}"
            input_file.write_bytes(content)
            logger.info("Summary: transcribing '{}' via Whisper", file.filename)
            try:
                text = client.transcribe(str(input_file), response_format="text")
            except RuntimeError as e:
                raise HTTPException(status_code=502, detail=f"Transkription fehlgeschlagen: {e}")
    else:
        extractor = EXTRACTORS.get(ext)
        if extractor is None:
            raise HTTPException(status_code=400, detail="Dateityp wird nicht unterstützt")
        try:
            text = extractor(content)
        except Exception as e:
            logger.exception("Text extraction error for file '{}'", file.filename)
            raise HTTPException(status_code=500, detail=f"Fehler beim Lesen der Datei: {str(e)}")

    text = text.strip()
    word_count = len(text.split())
    if word_count < _MIN_WORDS:
        raise HTTPException(
            status_code=422,
            detail=f"Inhalt zu kurz ({word_count} Wörter). Mindestens {_MIN_WORDS} Wörter erforderlich.",
        )

    too_long = len(text) > _CONTEXT_WARN_CHARS
    logger.info("Summary: {} words from '{}' (too_long={})", word_count, file.filename, too_long)

    # ── LLM summary ───────────────────────────────────────────────────────────
    try:
        summary = client.generate_summary(
            text,
            user_prompt=user_prompt.strip() or None,
            output_format=output_format,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if too_long:
        summary += (
            "\n\n⚠️ Hinweis: Der Inhalt war sehr umfangreich. "
            "Die Zusammenfassung könnte unvollständig sein."
        )

    stem = Path(file.filename).stem
    output_name = f"{stem}_zusammenfassung{_OUTPUT_EXT[output_format]}"
    out_ext = _OUTPUT_EXT[output_format]
    logger.info("Summary complete: '{}'", output_name)

    # Save result to job history (non-fatal)
    try:
        job_uuid = uuid.uuid4().hex
        user_id = current_user.get("user_id", 0)
        result_path = save_result_file(job_uuid, out_ext, summary.encode("utf-8"))
        db.create_job(job_uuid, user_id, "summary", file.filename)
        db.update_job_result(job_uuid, result_path, output_name)
        db.update_job_status(job_uuid, "success")
    except Exception:
        logger.exception("Job tracking failed for summary of '{}'", file.filename)

    encoded_name = quote(output_name, safe="")

    return Response(
        content=summary.encode("utf-8"),
        media_type=_OUTPUT_MIME[output_format],
        headers={
            "Content-Disposition": (
                f'attachment; filename="{encoded_name}"; '
                f"filename*=UTF-8''{encoded_name}"
            ),
        },
    )
