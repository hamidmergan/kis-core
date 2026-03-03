import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.storage import save_queue_file
from src.utils.file_validation import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, SCRIPT_MAX_CHARS
from src.utils.text_extraction import EXTRACTORS

router = APIRouter(tags=["script"])


@router.post("/script")
async def generate_script(
    request: Request,
    file: UploadFile = File(...),
    glossary_json: str = Form(""),
    user_prompt: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Nur .docx, .pptx, .md, .tex oder .txt erlaubt"
        )

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        raise HTTPException(status_code=400, detail="Dateityp wird nicht unterstützt")

    text = extractor(content)
    if len(text) > SCRIPT_MAX_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Dokument zu lang ({len(text):,} Zeichen). Bitte aufteilen (max. {SCRIPT_MAX_CHARS:,} Zeichen).".replace(",", "."),
        )

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)

    db.create_job(job_uuid, user_id, "script", file.filename)
    input_path = save_queue_file(job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_script
    run_script.delay(job_uuid, input_path, file.filename, glossary_json, user_prompt)

    logger.info("Script job {} queued for '{}'", job_uuid, file.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
