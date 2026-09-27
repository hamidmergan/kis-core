"""Celery task: render the final MP4 from edited scripts + stored PPTX."""

import json
import time
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.i18n import t
from src.limits import STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT
from src.storage import (
    clear_render_cache,
    get_job_file,
    load_result_meta,
    save_job_file,
    save_result_and_evict,
    save_result_meta,
)
from src.utils.heartbeat import job_heartbeat
from src.services.job_recovery import attempt_failed, still_mine
from src.services.screencast.naming import build_artifact_stem

from src.tasks._errors import handle_task_exception, is_upstream_busy, job_locale
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.tasks.screencast_tasks._pipeline import _run_render_pipeline
from src.tasks.screencast_tasks._queue import _maybe_dispatch_next
from src.tasks.screencast_tasks._shared import _JobCancelled, _stimme_festlegen


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
    tts_pin: dict | None = None,
) -> None:
    """Step 6 later compares against this to preselect what changed."""
    try:
        folientexte = json.loads(get_job_file(user_id, job_uuid, "scripts.txt"))
    except Exception:
        folientexte = []
    # Step 6 compares with the person's choice, the voice that really spoke stays in the pin.
    pin = tts_pin or {}
    save_job_file(user_id, job_uuid, "vertonter_stand.json", json.dumps({
        "scripts": scripts,
        "folientexte": folientexte,
        "voice_id": pin.get("requested_voice_id", voice_id),
        "provider_id": pin.get("requested_provider_id", provider_id),
        "tts_pin": tts_pin,
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
    soft_time_limit=STAGE_SOFT_TIME_LIMIT,
    time_limit=STAGE_TIME_LIMIT,
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
    versuch: int = 0,
):
    """Renders the finished MP4 from the scripts and the stored PPTX."""
    from celery.exceptions import SoftTimeLimitExceeded
    from fastapi import HTTPException
    try:
        if not still_mine(translate_job_uuid, versuch):
            raise StageLost(translate_job_uuid)
        clock = StageClock()
        job_row = db.get_job(translate_job_uuid)
        if not job_row:
            raise RuntimeError(f"Job {translate_job_uuid} not found")
        user_id = job_row["user_id"]
        # The first run decides the voice, every later stage, resume and retry of this run keeps it.
        tts_pin = _stimme_festlegen(user_id, translate_job_uuid, provider_id, voice_id, voice_label)
        provider_id, voice_id, voice_label = int(tts_pin["provider_id"]), tts_pin["voice_id"], tts_pin["voice_label"]
        db.update_job_status(translate_job_uuid, "running", progress={
            "step": "render", "voice_id": voice_id, "voice_label": voice_label, "provider_id": provider_id,
        })
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
            tts_pin=tts_pin,
            clock=clock,
            token=versuch,
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
            # gerendert_am is second precise and only steers the browser cache, not a file name.
            {**meta_existing, "result_stem": result_stem, "gerendert_am": int(time.time())},
        )
        with job_heartbeat(translate_job_uuid):
            save_result_and_evict(user_id, translate_job_uuid, result["result_path"], result_filename)
        db.update_job_status(translate_job_uuid, "success")
        _merke_vertonten_stand(
            user_id, translate_job_uuid, scripts, voice_id, provider_id,
            speed, slide_pause, subtitles, video_folien, tts_pin,
        )
        clear_render_cache(user_id, translate_job_uuid)

        logger.info("Screencast render task {} completed", translate_job_uuid)
        _maybe_dispatch_next(translate_job_uuid)

    except StageContinue:
        # The row stays running and keeps the slot, only the work moves on.
        args = [translate_job_uuid, scripts, voice_id, speed, slide_pause, original_filename,
                dpi, provider_id, voice_label, is_admin, subtitles,
                video_folien, neu_vertonen, versuch]
        continue_stage(self, args, translate_job_uuid)

    except StageLost:
        logger.info("Screencast {}: Etappe gehoert nicht mehr uns, nichts getan", translate_job_uuid)

    except _JobCancelled:
        logger.info("Screencast render task {} cancelled by user", translate_job_uuid)
        db.reset_job_to_awaiting(translate_job_uuid)
        _maybe_dispatch_next(translate_job_uuid)  # awaiting_user holds no slot -> start the next job

    except SoftTimeLimitExceeded:
        logger.warning("Screencast render task {} hit soft time limit", translate_job_uuid)
        job = db.get_job(translate_job_uuid)
        locale = (job and job.get("creator_locale")) or "de"
        attempt_failed(translate_job_uuid, t("job.timeoutRetry", locale))
        _maybe_dispatch_next(translate_job_uuid)

    except HTTPException as e:
        detail = str(getattr(e, "detail", e))
        logger.error("Screencast render task {} failed (HTTPException {}): {}", translate_job_uuid, e.status_code, detail)
        # Otherwise the raw provider message ends up on screen.
        voll = is_upstream_busy(detail)
        if voll:
            detail = t("job.upstreamBusy", job_locale(translate_job_uuid))
        attempt_failed(translate_job_uuid, detail, busy=voll)
        _maybe_dispatch_next(translate_job_uuid)
        raise

    except Exception as e:
        handle_task_exception(translate_job_uuid, e, task_label="Screencast render")
        _maybe_dispatch_next(translate_job_uuid)
        raise
