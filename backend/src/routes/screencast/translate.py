"""Translate-Endpoints: Translate-Queue, Text-Extraktion, PPTX→Bilder, korrigierter Upload."""

import base64
import json
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.limits import MAX_QUEUED_SCREENCAST_JOBS
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.services.screencast import (
    convert_slides_to_images_async,
    extract_text_per_slide,
    maybe_start_cleanup_task,
)
from src.storage import save_job_file, save_queue_file
from src.utils.file_validation import MAX_SCREENCAST_SLIDES, MAX_UPLOAD_BYTES

from src.routes.screencast._models import ExtractTextsRequest, PrepareRequest
from src.routes.screencast._shared import SCREENCAST_TOOLS, validate_upload

router = APIRouter(tags=["screencast: translate"])


def _enforce_queue_and_quota(user_id: int, current_user: dict) -> None:
    if db.count_all_jobs_for_tool(user_id, SCREENCAST_TOOLS) >= MAX_QUEUED_SCREENCAST_JOBS:
        raise HTTPException(
            status_code=409,
            detail=f"Du hast bereits {MAX_QUEUED_SCREENCAST_JOBS} Screencast-Jobs in der Warteschlange.",
        )
    enforce_tool_burst(user_id, "screencast")
    enforce_quota(user_id, "screencast", is_admin_user(current_user))


@router.post("/screencast/translate")
async def screencast_translate(
    request: Request,
    file: UploadFile = File(...),
    glossary_json: str = Form(""),
    source_lang: str = Form("DE"),
    target_lang: str = Form("EN-US"),
    current_user: dict = Depends(get_current_user),
):
    """Queue a translate job: translate PPTX DE→EN, extract slide texts (+ images)."""
    validate_upload(file.filename)
    maybe_start_cleanup_task()

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    pptx_bytes = await file.read()
    if not pptx_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    user_id = current_user.get("user_id", 0)
    _enforce_queue_and_quota(user_id, current_user)

    job_uuid = uuid.uuid4().hex
    filename = file.filename or "screencast.pptx"
    db.create_job(job_uuid, user_id, "screencast_translate", filename, username=current_user.get("username", "unknown"))
    input_path = save_queue_file(job_uuid, ".pptx", pptx_bytes)
    db.set_job_input_path(job_uuid, input_path)

    save_job_file(job_uuid, "queue_params.json", json.dumps({
        "dispatch_as": "translate",
        "input_path": input_path,
        "filename": filename,
        "glossary_json": glossary_json,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }).encode())
    db.update_job_status(job_uuid, "queued")
    from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
    dispatch_next_screencast_job_for_user(user_id)
    logger.info("Screencast translate job submitted: job_uuid={}, file={}", job_uuid, filename)

    return {"job_uuid": job_uuid}


@router.post("/screencast/extract-texts")
async def screencast_extract_texts(body: ExtractTextsRequest):
    """Extract slide texts from a PPTX (base64-encoded)."""
    try:
        pptx_bytes = base64.b64decode(body.pptx_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige PPTX-Daten (Base64)")

    logger.info("Screencast/extract-texts: extracting texts from PPTX")
    slide_texts = extract_text_per_slide(pptx_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")

    if len(slide_texts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(slide_texts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    return {
        "slide_count": len(slide_texts),
        "slide_texts": slide_texts,
    }


@router.post("/screencast/prepare")
async def screencast_prepare(body: PrepareRequest):
    """Convert translated PPTX to slide images."""
    try:
        pptx_bytes = base64.b64decode(body.translated_pptx_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Ungültige PPTX-Daten (Base64)")

    logger.info("Screencast/prepare: converting PPTX to images")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        translated_pptx_path = tmp / "translated.pptx"
        translated_pptx_path.write_bytes(pptx_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()

        try:
            slide_image_paths = await convert_slides_to_images_async(
                translated_pptx_path, img_dir
            )
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

    return {"slide_images": slide_images_b64}


@router.post("/screencast/upload-corrected")
async def screencast_upload_corrected(
    request: Request,
    file: UploadFile = File(...),
    translate_job_uuid: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Upload a corrected PPTX, save to temp storage + job folder, extract texts and slide images."""
    validate_upload(file.filename)
    maybe_start_cleanup_task()

    pptx_bytes = await file.read()
    if not pptx_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    logger.info("Screencast/upload-corrected: '{}' ({} bytes)", file.filename, len(pptx_bytes))

    # Validate job ownership if translate_job_uuid provided
    if translate_job_uuid:
        job = db.get_job(translate_job_uuid)
        if not job:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        if job["user_id"] != current_user.get("user_id", 0):
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")

    slide_texts = extract_text_per_slide(pptx_bytes)
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Keine Slides in der Präsentation gefunden")

    if len(slide_texts) > MAX_SCREENCAST_SLIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Zu viele Folien ({len(slide_texts)}). Maximum: {MAX_SCREENCAST_SLIDES} Folien.",
        )

    if translate_job_uuid:
        # Existing job: save as corrected.pptx (user re-uploaded after translation)
        save_job_file(translate_job_uuid, "corrected.pptx", pptx_bytes)
        logger.info("Saved corrected.pptx to job folder {}", translate_job_uuid)
    else:
        # No job yet (EN path): create a new translate job and save PPTX as translated.pptx
        user_id = current_user.get("user_id", 0)
        _enforce_queue_and_quota(user_id, current_user)
        translate_job_uuid = uuid.uuid4().hex
        db.create_job(translate_job_uuid, user_id, "screencast_translate", file.filename or "screencast.pptx", username=current_user.get("username", "unknown"))
        save_job_file(translate_job_uuid, "translated.pptx", pptx_bytes)
        save_job_file(translate_job_uuid, "scripts.txt", json.dumps(slide_texts, ensure_ascii=False, indent=2).encode("utf-8"))
        db.update_job_status(translate_job_uuid, "awaiting_user")
        db.update_job_expiry(translate_job_uuid, 168)
        logger.info("Created translate job {} for EN upload ({})", translate_job_uuid, file.filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pptx_path = tmp / "upload.pptx"
        pptx_path.write_bytes(pptx_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()
        try:
            slide_image_paths = await convert_slides_to_images_async(pptx_path, img_dir)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

    return {
        "translate_job_uuid": translate_job_uuid,
        "slide_texts": slide_texts,
        "slide_images": slide_images_b64,
    }
