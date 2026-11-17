"""Celery task: translate PPTX DE->EN, extract slide texts, set awaiting_user."""

import asyncio
import base64
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
from src.services.job_statistik import anbieter_und_modell, messe, notiere
from src.utils.heartbeat import job_heartbeat

from src.limits import STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT
from src.tasks._errors import handle_task_exception
from src.tasks.general_tasks import parse_glossary
from src.tasks.screencast_tasks._queue import _maybe_dispatch_next


def _translation_service(provider_id: int | None, glossary_json: str):
    """The translator of this run and the provider it settled on."""
    from src.dependencies import get_translate_client_for_provider, get_translation_providers
    from src.services.translation import TranslationService

    # The choice is made here so the admin display names the right provider.
    if provider_id is None:
        verfuegbare = get_translation_providers()
        provider_id = verfuegbare[0]["id"] if verfuegbare else None

    translation_client, glossary = get_translate_client_for_provider(
        provider_id, glossary_entries=parse_glossary(glossary_json) or None
    )
    if translation_client is None:
        raise RuntimeError("No translation provider configured")
    return TranslationService(deepl_client=translation_client, glossary=glossary), provider_id


def _slide_images_b64(job_uuid: str, translated_bytes: bytes, convert) -> list[str]:
    """The translated slides as pictures for the review step."""
    with tempfile.TemporaryDirectory() as tmpdir, job_heartbeat(job_uuid):
        tmp = Path(tmpdir)
        pptx_path = tmp / "translated.pptx"
        pptx_path.write_bytes(translated_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()
        slide_image_paths = asyncio.run(convert(pptx_path, img_dir))
        return [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]


@celery_app.task(
    bind=True,
    name="screencast.translate",
    queue="screencast",
    soft_time_limit=STAGE_SOFT_TIME_LIMIT,
    time_limit=STAGE_TIME_LIMIT,
)
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

        from src.translators.pptx import translate_pptx

        service, provider_id = _translation_service(provider_id, glossary_json)
        # A heartbeat, otherwise the watchdog takes a slow translation for a crash.
        with job_heartbeat(job_uuid), messe(user_id, job_uuid, "uebersetzung") as zahlen:
            zahlen.update(anbieter_und_modell(provider_id or 0, "doc_translate"))
            zahlen["quelle"] = source_lang
            zahlen["ziel"] = target_lang
            translated_bytes = translate_pptx(pptx_bytes, source_lang, target_lang, service)

        from src.services.screencast import convert_slides_to_images_async, extract_text_per_slide

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = extract_text_per_slide(translated_bytes)
        if not slide_texts:
            locale = job_row.get("creator_locale") or "de"
            raise ValueError(t("screencast.noSlides", locale))

        # For the review step: which slides the translation did not touch.
        from src.services.screencast.review import find_unchanged_slides
        unchanged_slides = find_unchanged_slides(
            extract_text_per_slide(pptx_bytes), slide_texts
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
        slide_images_b64 = _slide_images_b64(job_uuid, translated_bytes, convert_slides_to_images_async)

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
