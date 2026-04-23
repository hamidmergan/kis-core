"""Celery-Task: PPTX DE→EN übersetzen, Slide-Texte extrahieren, awaiting_user setzen."""

import asyncio
import json
import tempfile
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import (
    delete_file,
    get_file,
    save_job_file,
    save_result_and_evict,
    save_result_json,
)

from src.tasks.screencast_tasks._queue import _maybe_dispatch_next
from src.tasks.screencast_tasks._shared import _get_screencast_helpers


@celery_app.task(bind=True, name="screencast.translate", queue="screencast")
def run_screencast_translate(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    glossary_json: str,
    fast_mode: bool,
    source_lang: str = "DE",
    target_lang: str = "EN-US",
):
    """Translate PPTX DE→EN, extract slide texts, save artifacts, set awaiting_user."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "translate"})

        pptx_bytes = get_file(input_path)

        # Save original DE PPTX immediately
        save_job_file(job_uuid, "original.pptx", pptx_bytes)

        from src.routes.translate import translate_pptx_content
        translated_bytes = translate_pptx_content(
            pptx_bytes, filename, glossary_json, source_lang, target_lang
        )

        (
            IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart,
            _extract_text_per_slide,
        ) = _get_screencast_helpers()

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = _extract_text_per_slide(translated_bytes)
        if not slide_texts:
            raise ValueError("Keine Slides in der Präsentation gefunden")

        # Save translated PPTX + scripts to job folder immediately
        save_job_file(job_uuid, "translated.pptx", translated_bytes)
        save_job_file(job_uuid, "scripts.txt", json.dumps(slide_texts, ensure_ascii=False, indent=2).encode("utf-8"))

        if fast_mode:
            result = {
                "slide_count": len(slide_texts),
                "slide_texts": slide_texts,
                "slide_images": [],
            }
        else:
            db.update_job_status(job_uuid, "running", progress={"step": "images"})
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                pptx_path = tmp / "translated.pptx"
                pptx_path.write_bytes(translated_bytes)
                img_dir = tmp / "images"
                img_dir.mkdir()
                slide_image_paths = asyncio.run(_convert_slides_to_images_async(pptx_path, img_dir))
                import base64
                slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

            result = {
                "slide_count": len(slide_texts),
                "slide_texts": slide_texts,
                "slide_images": slide_images_b64,
            }

        result_path = save_result_json(job_uuid, result)
        save_result_and_evict(job_uuid, result_path, f"{Path(filename).stem}_translate.json")

        # awaiting_user: user must review scripts before render starts
        db.update_job_status(job_uuid, "awaiting_user")
        db.update_job_expiry(job_uuid, 168)  # 7 days — no resources held while waiting
        _maybe_dispatch_next(job_uuid)  # awaiting_user hält keinen Slot → nächsten Job starten

        # Clean up input file
        delete_file(input_path)

        logger.info("Screencast translate task {} completed: {} slides", job_uuid, len(slide_texts))

    except Exception as e:
        logger.error("Screencast translate task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise
