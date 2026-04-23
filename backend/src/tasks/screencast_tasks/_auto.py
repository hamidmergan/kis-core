"""Celery-Task: Full-Auto-Pipeline (translate → scripts → TTS → render)."""

import asyncio
import json
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.limits import SCREENCAST_AUTO_SOFT_TIME_LIMIT, SCREENCAST_AUTO_TIME_LIMIT
from src.storage import (
    clear_tts_audio_cache,
    delete_file,
    get_file,
    save_job_file,
    save_result_and_evict,
)
from src.utils.heartbeat import job_heartbeat

from src.tasks.screencast_tasks._pipeline import _run_render_pipeline
from src.tasks.screencast_tasks._queue import _maybe_dispatch_next
from src.tasks.screencast_tasks._shared import _get_screencast_helpers


@celery_app.task(
    bind=True,
    name="screencast.auto",
    queue="screencast",
    acks_late=True,
    soft_time_limit=SCREENCAST_AUTO_SOFT_TIME_LIMIT,
    time_limit=SCREENCAST_AUTO_TIME_LIMIT,
)
def run_screencast_auto(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    voice_id: str,
    speed: float,
    glossary_json: str,
    provider: str = "elevenlabs",
    voice_label: str = "",
    source_lang: str = "DE",
    target_lang: str = "EN-US",
    dpi: int = 100,
):
    """Full auto pipeline: translate → scripts → TTS → render."""
    from celery.exceptions import SoftTimeLimitExceeded
    try:
        db.update_job_status(job_uuid, "running", progress={
            "step": "translate", "voice_id": voice_id, "voice_label": voice_label, "provider": provider,
        })

        pptx_bytes = get_file(input_path)

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

        save_job_file(job_uuid, "translated.pptx", translated_bytes)

        # Generate scripts via KISSKI
        db.update_job_status(job_uuid, "running", progress={"step": "scripts", "total": len(slide_texts)})
        from src.services.kisski_client import KisskiClient
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _model, _provider = _resolve_llm_provider()
        if not _api_key:
            raise RuntimeError("Kein LLM-Provider konfiguriert")
        kisski_client = KisskiClient(
            api_key=_api_key,
            base_url=_base_url,
            model=_model,
            provider=_provider,
        )

        glossary_dict = None
        if glossary_json:
            try:
                glossary_dict = json.loads(glossary_json)
            except Exception:
                pass

        with job_heartbeat(job_uuid):
            scripts = asyncio.run(
                _generate_all_scripts_async(
                    slide_texts, kisski_client, glossary=glossary_dict, source_lang=source_lang, target_lang=target_lang
                )
            )

        with job_heartbeat(job_uuid):
            result = _run_render_pipeline(
                job_uuid=job_uuid,
                scripts=scripts,
                voice_id=voice_id,
                speed=speed,
                slide_pause=0.5,
                dpi=dpi,
                provider=provider,
            )

        result_filename = f"{Path(filename).stem}.mp4"
        with job_heartbeat(job_uuid):
            save_result_and_evict(job_uuid, result["result_path"], result_filename)
        db.update_job_status(job_uuid, "success")
        clear_tts_audio_cache(job_uuid)

        # Clean up input file
        delete_file(input_path)

        logger.info("Screencast auto task {} completed: {}", job_uuid, result_filename)
        _maybe_dispatch_next(job_uuid)

    except SoftTimeLimitExceeded:
        logger.warning("Screencast auto task {} hit soft time limit", job_uuid)
        db.update_job_status(job_uuid, "failed", error_message="Zeitlimit überschritten. Bitte 'Wiederholen' klicken.")
        _maybe_dispatch_next(job_uuid)

    except Exception as e:
        logger.error("Screencast auto task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        _maybe_dispatch_next(job_uuid)
        raise


async def _generate_all_scripts_async(slide_texts, kisski_client, glossary=None, source_lang="DE", target_lang="EN-US"):
    """Async wrapper for batch script generation (called via asyncio.run)."""
    return kisski_client.generate_scripts_batch(slide_texts, glossary, source_lang=source_lang, target_lang=target_lang)
