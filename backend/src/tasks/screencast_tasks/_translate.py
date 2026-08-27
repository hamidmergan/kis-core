"""Celery task: translate PPTX DE->EN, extract slide texts, set awaiting_user."""

import asyncio
import json
import tempfile
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.i18n import t
from src.storage import (
    delete_file,
    get_file,
    load_result_meta,
    save_job_file,
    save_result_and_evict,
    save_result_json,
    save_result_meta,
)
from src.services.screencast.naming import translate_stem
from src.services.screencast.statistik import anbieter_und_modell, messe, notiere
from src.utils.heartbeat import job_heartbeat

from src.tasks._errors import handle_task_exception
from src.tasks.screencast_tasks._queue import _maybe_dispatch_next
from src.tasks.screencast_tasks._shared import _get_screencast_helpers


@celery_app.task(bind=True, name="screencast.translate", queue="screencast")
def run_screencast_translate(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    glossary_json: str,
    source_lang: str = "DE",
    target_lang: str = "EN-US",
    provider_id: int | None = None,
):
    """Translate PPTX DE→EN, extract slide texts, save artifacts, set awaiting_user."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "translate"})
        job_row = db.get_job(job_uuid)
        if not job_row:
            raise RuntimeError(f"Job {job_uuid} not found")
        user_id = job_row["user_id"]

        pptx_bytes = get_file(input_path)

        # Save original DE PPTX immediately
        save_job_file(user_id, job_uuid, "original.pptx", pptx_bytes)

        # Resolve translation provider
        from src.dependencies import get_translate_client_for_provider
        from src.services.translation import TranslationService
        from src.translators.pptx import translate_pptx

        glossary_entries: dict = {}
        if glossary_json:
            try:
                entries = json.loads(glossary_json)
                if isinstance(entries, dict):
                    glossary_entries = entries
            except (json.JSONDecodeError, TypeError):
                pass

        # The choice is made here so the admin display names the right provider.
        if provider_id is None:
            from src.dependencies import get_translation_providers
            verfuegbare = get_translation_providers()
            provider_id = verfuegbare[0]["id"] if verfuegbare else None

        translation_client, glossary = get_translate_client_for_provider(
            provider_id, glossary_entries=glossary_entries or None
        )
        if translation_client is None:
            raise RuntimeError("No translation provider configured")

        service = TranslationService(deepl_client=translation_client, glossary=glossary)
        # A heartbeat, otherwise the watchdog takes a slow translation for a crash.
        with job_heartbeat(job_uuid), messe(user_id, job_uuid, "uebersetzung") as zahlen:
            zahlen.update(anbieter_und_modell(provider_id or 0, "doc_translate"))
            zahlen["quelle"] = source_lang
            zahlen["ziel"] = target_lang
            translated_bytes = translate_pptx(pptx_bytes, source_lang, target_lang, service)

        (
            IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart,
            _extract_text_per_slide,
            _create_outro_image, _get_image_dimensions,
        ) = _get_screencast_helpers()

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = _extract_text_per_slide(translated_bytes)
        if not slide_texts:
            locale = job_row.get("creator_locale") or "de"
            raise ValueError(t("screencast.noSlides", locale))

        # For the review step: which slides the translation did not touch.
        from src.services.screencast.review import find_unchanged_slides
        unchanged_slides = find_unchanged_slides(
            _extract_text_per_slide(pptx_bytes), slide_texts
        )
        if unchanged_slides:
            logger.info(
                "Screencast translate {}: {} Folie(n) unverändert: {}",
                job_uuid, len(unchanged_slides), unchanged_slides,
            )

        # The duration is already recorded, the slide counts are only known now.
        zahlen["folien"] = len(slide_texts)
        zahlen["unveraenderte_folien"] = len(unchanged_slides)
        notiere(user_id, job_uuid, "uebersetzung", zahlen)

        # Save translated PPTX + scripts to job folder immediately
        save_job_file(user_id, job_uuid, "translated.pptx", translated_bytes)
        save_job_file(user_id, job_uuid, "scripts.txt", json.dumps(slide_texts, ensure_ascii=False, indent=2).encode("utf-8"))

        db.update_job_status(job_uuid, "running", progress={"step": "images"})
        with tempfile.TemporaryDirectory() as tmpdir, job_heartbeat(job_uuid):
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
            "unchanged_slides": unchanged_slides,
        }

        result_path = save_result_json(user_id, job_uuid, result)
        save_result_and_evict(user_id, job_uuid, result_path, f"{Path(filename).stem}_translate.json")

        # The name stem is translated once and applies to MP4, PPTX and ZIP.
        translated = translate_stem(filename, source_lang, target_lang, service=service)
        # Append, do not overwrite, otherwise the translation statistics are lost.
        save_result_meta(user_id, job_uuid, {
            **(load_result_meta(user_id, job_uuid) or {}),
            "translated_stem": translated, "target_lang": target_lang,
        })

        # Waits for the review, the watchdog picks up whatever is left behind.
        db.update_job_status(job_uuid, "awaiting_user")
        _maybe_dispatch_next(job_uuid)  # awaiting_user holds no slot -> start the next job

        # Clean up input file
        delete_file(input_path)

        logger.info("Screencast translate task {} completed: {} slides", job_uuid, len(slide_texts))

    except Exception as e:
        handle_task_exception(job_uuid, e, task_label="Screencast translate")
        raise
