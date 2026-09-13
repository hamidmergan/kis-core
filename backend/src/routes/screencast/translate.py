"""Translate-Endpoints: Translate-Queue, Text-Extraktion, PPTX→Bilder, korrigierter Upload."""

import base64
import json
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
from src.services.screencast import (
    convert_slides_to_images_async,
    extract_text_per_slide,
    maybe_start_cleanup_task,
)
from src.storage import get_job_file, save_job_file, save_job_file_from_path, save_queue_file_from_path
from src.utils.file_validation import validate_or_raise
from src.services.open_jobs import enforce_open_jobs
from src.services.tool_limits import (
    max_screencast_slides,
    max_upload_bytes,
)
from src.utils.upload_stream import stream_upload_to_path

from src.routes.screencast._shared import SCREENCAST_TOOLS, validate_upload, vertonung_verwerfen

router = APIRouter(tags=["screencast: translate"])


def _enforce_queue_and_quota(user_id: int, current_user: dict, locale: str = "de") -> None:
    enforce_open_jobs(user_id, locale)
    enforce_tool_burst(user_id, "screencast", locale)
    enforce_quota(user_id, "screencast", is_admin_user(current_user), locale)


@router.post("/screencast/translate")
async def screencast_translate(
    request: Request,
    file: UploadFile = File(...),
    glossary_json: str = Form(""),
    source_lang: str = Form("DE"),
    target_lang: str = Form("EN-US"),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Queue a translate job: translate PPTX DE→EN, extract slide texts (+ images)."""
    validate_upload(file.filename, locale)
    maybe_start_cleanup_task()

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > max_upload_bytes():
        raise HTTPException(status_code=413, detail=t("file.tooLargeMb", locale, max=max_upload_bytes() // (1024 * 1024)))

    # Stream to disk, a PPTX with media quickly gets huge.
    with tempfile.TemporaryDirectory(prefix="screencast_upload_") as tmpdir:
        tmp_path = os.path.join(tmpdir, "input.pptx")
        total, head = await stream_upload_to_path(file, tmp_path, max_upload_bytes(), locale)
        if not total:
            raise HTTPException(status_code=400, detail=t("file.empty", locale))
        validate_or_raise(head, ".pptx", locale)

        user_id = current_user.get("user_id", 0)
        _enforce_queue_and_quota(user_id, current_user, locale)

        job_uuid = uuid.uuid4().hex
        filename = file.filename or "screencast.pptx"
        db.create_job(job_uuid, user_id, "screencast_translate", filename, locale=locale)
        input_path = save_queue_file_from_path(user_id, job_uuid, ".pptx", tmp_path)
        db.set_job_input_path(job_uuid, input_path)

    save_job_file(user_id, job_uuid, "queue_params.json", json.dumps({
        "dispatch_as": "translate",
        "input_path": input_path,
        "filename": filename,
        "glossary_json": glossary_json,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "provider_id": provider_id,
    }).encode())
    db.update_job_status(job_uuid, "queued")
    from src.tasks.screencast_tasks import dispatch_next_screencast_job_for_user
    dispatch_next_screencast_job_for_user(user_id)
    logger.info("Screencast translate job submitted: job_uuid={}, file={}", job_uuid, filename)

    return {"job_uuid": job_uuid}




@router.post("/screencast/upload-corrected")
async def screencast_upload_corrected(
    request: Request,
    file: UploadFile = File(...),
    translate_job_uuid: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Upload a corrected PPTX, save to temp storage + job folder, extract texts and slide images."""
    validate_upload(file.filename, locale)
    maybe_start_cleanup_task()

    # One temp copy serves everything: check, text extraction, job folder and rendering.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pptx_path = tmp / "upload.pptx"
        total, head = await stream_upload_to_path(file, str(pptx_path), max_upload_bytes(), locale)
        if not total:
            raise HTTPException(status_code=400, detail=t("file.empty", locale))
        validate_or_raise(head, ".pptx", locale)

        logger.info("Screencast/upload-corrected: '{}' ({} bytes)", file.filename, total)

        # Validate job ownership if translate_job_uuid provided
        if translate_job_uuid:
            job = db.get_job(translate_job_uuid)
            if not job:
                raise HTTPException(status_code=404, detail=t("job.notFound", locale))
            if job["user_id"] != current_user.get("user_id", 0):
                raise HTTPException(status_code=403, detail=t("job.accessDenied", locale))

        slide_texts = extract_text_per_slide(str(pptx_path))
        if not slide_texts:
            raise HTTPException(status_code=400, detail=t("screencast.noSlides", locale))

        folien_grenze = max_screencast_slides()
        if len(slide_texts) > folien_grenze:
            raise HTTPException(
                status_code=400,
                detail=t(
                    "screencast.tooManySlides",
                    locale,
                    count=len(slide_texts),
                    max=folien_grenze,
                ),
            )

        if translate_job_uuid:
            # The slide number is the key between image, script and audio.
            try:
                alte_anzahl = len(json.loads(get_job_file(job["user_id"], translate_job_uuid, "scripts.txt")))
            except Exception:
                alte_anzahl = 0
            if alte_anzahl and len(slide_texts) != alte_anzahl:
                raise HTTPException(
                    status_code=400,
                    detail=t("screencast.folienzahlPasstNicht", locale,
                             neu=len(slide_texts), alt=alte_anzahl),
                )
            # Existing job: save as corrected.pptx (user re-uploaded after translation)
            save_job_file_from_path(job["user_id"], translate_job_uuid, "corrected.pptx", str(pptx_path))
            # Without this scripts.txt would keep the texts from before the correction.
            save_job_file(job["user_id"], translate_job_uuid, "scripts.txt",
                          json.dumps(slide_texts, ensure_ascii=False, indent=2).encode("utf-8"))
            # New slides, old audio would be wrong, only now that the slide count check passed.
            vertonung_verwerfen(job["user_id"], translate_job_uuid)
            logger.info("Saved corrected.pptx to job folder {}", translate_job_uuid)
        else:
            # No job yet (EN path): create a new translate job and save PPTX as translated.pptx
            user_id = current_user.get("user_id", 0)
            _enforce_queue_and_quota(user_id, current_user, locale)
            translate_job_uuid = uuid.uuid4().hex
            db.create_job(translate_job_uuid, user_id, "screencast_translate", file.filename or "screencast.pptx", locale=locale)
            save_job_file_from_path(user_id, translate_job_uuid, "translated.pptx", str(pptx_path))
            save_job_file(user_id, translate_job_uuid, "scripts.txt", json.dumps(slide_texts, ensure_ascii=False, indent=2).encode("utf-8"))
            db.update_job_status(translate_job_uuid, "awaiting_user")
            logger.info("Created translate job {} for EN upload ({})", translate_job_uuid, file.filename)

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
