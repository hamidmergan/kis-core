"""Celery task: render the final MP4 from edited scripts + stored PPTX."""

import json
import time
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.i18n import t
from src.limits import SCREENCAST_SOFT_TIME_LIMIT, SCREENCAST_TIME_LIMIT
from src.storage import (
    clear_render_cache,
    get_job_file,
    load_result_meta,
    save_job_file,
    save_result_and_evict,
    save_result_meta,
)
from src.utils.heartbeat import job_heartbeat
from src.services.screencast.naming import build_artifact_stem

from src.tasks._errors import handle_task_exception, is_upstream_busy, job_locale
from src.tasks.screencast_tasks._pipeline import _run_render_pipeline
from src.tasks.screencast_tasks._queue import _maybe_dispatch_next
from src.tasks.screencast_tasks._shared import _JobCancelled


def _merke_vertonten_stand(
    user_id: int,
    job_uuid: str,
    scripts: list[str],
    voice_id: str,
    provider_id: int,
    speed: float,
    slide_pause: float,
    subtitles: bool,
    video_folien: list[int] | None,
) -> None:
    """Schritt 6 vergleicht spaeter hiergegen, um Geaendertes vorauszuwaehlen."""
    try:
        folientexte = json.loads(get_job_file(user_id, job_uuid, "scripts.txt"))
    except Exception:
        folientexte = []
    save_job_file(user_id, job_uuid, "vertonter_stand.json", json.dumps({
        "scripts": scripts,
        "folientexte": folientexte,
        "voice_id": voice_id,
        "provider_id": provider_id,
        "target_lang": (load_result_meta(user_id, job_uuid) or {}).get("target_lang", ""),
        "speed": speed,
        "slide_pause": slide_pause,
        "subtitles": subtitles,
        "video_folien": sorted(video_folien) if video_folien is not None else list(range(len(scripts))),
    }, ensure_ascii=False).encode())


@celery_app.task(
    bind=True,
    name="screencast.render",
    queue="screencast",
    acks_late=True,
    max_retries=7,
    soft_time_limit=SCREENCAST_SOFT_TIME_LIMIT,
    time_limit=SCREENCAST_TIME_LIMIT,
)
def run_screencast_render(
    self,
    translate_job_uuid: str,
    scripts: list[str],
    voice_id: str,
    speed: float,
    slide_pause: float,
    original_filename: str = "screencast",
    dpi: int = 100,
    provider_id: int = 0,
    voice_label: str = "",
    is_admin: bool = False,
    subtitles: bool = False,
    video_folien: list[int] | None = None,
    neu_vertonen: list[int] | None = None,
):
    """Render final MP4 from edited scripts and stored PPTX.

    Reads PPTX from the translate job's folder (corrected.pptx or translated.pptx).
    All artifacts are saved to the same folder (single-folder workflow).
    """
    from celery.exceptions import Retry, SoftTimeLimitExceeded
    from fastapi import HTTPException
    try:
        db.update_job_status(translate_job_uuid, "running", progress={
            "step": "render", "voice_id": voice_id, "voice_label": voice_label, "provider_id": provider_id,
        })
        job_row = db.get_job(translate_job_uuid)
        if not job_row:
            raise RuntimeError(f"Job {translate_job_uuid} not found")
        user_id = job_row["user_id"]
        with job_heartbeat(translate_job_uuid):
            result = _run_render_pipeline(
                job_uuid=translate_job_uuid,
                scripts=scripts,
                voice_id=voice_id,
                speed=speed,
                slide_pause=slide_pause,
                dpi=dpi,
                provider_id=provider_id,
                is_admin=is_admin,
                subtitles=subtitles,
                voice_label=voice_label,
                video_folien=video_folien,
                neu_vertonen=neu_vertonen,
            )

        meta_existing = load_result_meta(user_id, translate_job_uuid) or {}
        translated_stem = meta_existing.get("translated_stem") or (
            Path(original_filename).stem if original_filename else "screencast"
        )
        result_stem = build_artifact_stem(translated_stem)
        result_filename = f"{result_stem}.mp4"
        save_result_meta(
            user_id,
            translate_job_uuid,
            # gerendert_am ist sekundengenau und steuert nur den Browser-Zwischenspeicher, kein Dateiname.
            {**meta_existing, "result_stem": result_stem, "gerendert_am": int(time.time())},
        )
        with job_heartbeat(translate_job_uuid):
            save_result_and_evict(user_id, translate_job_uuid, result["result_path"], result_filename)
        db.update_job_status(translate_job_uuid, "success")
        _merke_vertonten_stand(
            user_id, translate_job_uuid, scripts, voice_id, provider_id,
            speed, slide_pause, subtitles, video_folien,
        )
        clear_render_cache(user_id, translate_job_uuid)

        logger.info("Screencast render task {} completed", translate_job_uuid)
        _maybe_dispatch_next(translate_job_uuid)

    except _JobCancelled:
        logger.info("Screencast render task {} cancelled by user", translate_job_uuid)
        db.reset_job_to_awaiting(translate_job_uuid)
        _maybe_dispatch_next(translate_job_uuid)  # awaiting_user holds no slot -> start the next job

    except SoftTimeLimitExceeded:
        logger.warning("Screencast render task {} hit soft time limit", translate_job_uuid)
        job = db.get_job(translate_job_uuid)
        locale = (job and job.get("creator_locale")) or "de"
        db.update_job_status(translate_job_uuid, "failed", error_message=t("job.timeoutRetry", locale))
        _maybe_dispatch_next(translate_job_uuid)

    except HTTPException as e:
        # Transient upstream TTS error (5xx): requeue with exponential backoff.
        # Already-cached slide audios survive the retry via render_cache/, so only
        # the failed slide(s) re-synthesize on the next attempt.
        detail = str(getattr(e, "detail", e))
        is_tts_transient = e.status_code == 502 and "TTS" in detail
        if is_tts_transient and self.request.retries < 5:
            countdown = 60 * (2 ** self.request.retries)  # 1m, 2m, 4m, 8m, 16m
            logger.warning(
                "Screencast {}: TTS upstream error (attempt {}/{}), retrying in {}s — {}",
                translate_job_uuid, self.request.retries + 1, 5, countdown, detail,
            )
            db.update_job_status(translate_job_uuid, "running", progress={
                "step": "tts_retry_pending",
                "retry_in_seconds": countdown,
                "attempt": self.request.retries + 1,
                "max_attempts": 5,
            })
            raise self.retry(exc=e, countdown=countdown, max_retries=5)
        logger.error("Screencast render task {} failed (HTTPException {}): {}", translate_job_uuid, e.status_code, detail)
        # Nach dem letzten Versuch steht hier sonst die rohe Meldung der Vertonung
        # im Bildschirm, etwa "TTS API error (500)".
        if is_upstream_busy(detail):
            detail = t("job.upstreamBusy", job_locale(translate_job_uuid))
        db.update_job_status(translate_job_uuid, "failed", error_message=detail)
        _maybe_dispatch_next(translate_job_uuid)
        raise

    except Retry:
        raise  # Celery's own retry signal — let it propagate without overwriting status

    except Exception as e:
        handle_task_exception(translate_job_uuid, e, task_label="Screencast render")
        _maybe_dispatch_next(translate_job_uuid)
        raise
