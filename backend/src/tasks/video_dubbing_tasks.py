"""Celery tasks: Video dubbing via ElevenLabs Dubbing API.

Architecture:
  1. submit_dubbing   – uploads file, gets dubbing_id, frees worker immediately
  2. poll_dubbing_jobs – Beat task (every 15s): checks all pending dubbing jobs
  3. download_dubbing  – triggered by poll when ElevenLabs reports "dubbed"
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import delete_file, get_file, save_result_file, save_result_meta, save_result_and_evict


@celery_app.task(bind=True, name="video_dubbing.submit", queue="dubbing")
def submit_dubbing(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    source_lang: str,
    target_lang: str,
    drop_background_audio: bool,
    num_speakers: int,
    soft_subtitles: bool,
):
    """Submit video to ElevenLabs. Worker freed immediately after submit."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "submit"})

        file_bytes = get_file(input_path)
        ext = Path(filename).suffix.lower()

        from src.routes.video_dubbing import (
            _get_api_key,
            _submit_dubbing_job,
            VIDEO_DUBBING_VIDEO_EXTENSIONS,
        )

        is_video = ext in VIDEO_DUBBING_VIDEO_EXTENSIONS
        api_key = _get_api_key()
        stem = Path(filename).stem

        dubbing_id = _submit_dubbing_job(
            api_key, file_bytes, filename, ext,
            source_lang, target_lang, drop_background_audio, num_speakers,
        )
        logger.info("Dubbing submitted: id='{}' for job {}", dubbing_id, job_uuid)

        # Store all params needed for download in progress — Beat will pick this up
        db.update_job_status(job_uuid, "running", progress={
            "step": "dubbing",
            "dubbing_id": dubbing_id,
            "target_lang": target_lang,
            "is_video": is_video,
            "soft_subtitles": soft_subtitles,
            "stem": stem,
            "input_path": input_path,
        })
        # Worker slot freed here — no polling in this task

    except Exception as e:
        logger.error("Dubbing submit task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


@celery_app.task(name="video_dubbing.poll", queue="dubbing")
def poll_dubbing_jobs():
    """Beat task (every 15s): poll ElevenLabs for all pending dubbing jobs."""
    pending_jobs = db.get_pending_dubbing_jobs()
    if not pending_jobs:
        return

    from src.routes.video_dubbing import _get_api_key, _check_dubbing_status_once
    try:
        api_key = _get_api_key()
    except Exception as e:
        logger.error("Dubbing poll: cannot get API key: {}", e)
        return

    for job in pending_jobs:
        job_uuid = job["job_uuid"]
        progress = json.loads(job["progress"] or "{}")
        dubbing_id = progress.get("dubbing_id")
        if not dubbing_id:
            continue
        try:
            status = _check_dubbing_status_once(api_key, dubbing_id)
            logger.info("Dubbing poll {}: status='{}'", job_uuid, status)
            if status == "dubbed":
                download_dubbing.apply_async(args=[job_uuid], queue="dubbing")
            elif status in ("failed", "error"):
                db.update_job_status(
                    job_uuid, "failed",
                    error_message="ElevenLabs Dubbing fehlgeschlagen",
                )
        except Exception as e:
            logger.error("Dubbing poll error for job {}: {}", job_uuid, e)


@celery_app.task(bind=True, name="video_dubbing.download", queue="dubbing")
def download_dubbing(self, job_uuid: str):
    """Download dubbed result from ElevenLabs and save to storage."""
    try:
        job = db.get_job(job_uuid)
        if not job or job["status"] != "running":
            logger.info("Download dubbing {}: job gone or cancelled, skipping", job_uuid)
            return

        progress = json.loads(job["progress"] or "{}")
        dubbing_id = progress.get("dubbing_id")
        target_lang = progress.get("target_lang")
        is_video = progress.get("is_video", False)
        soft_subtitles = progress.get("soft_subtitles", False)
        stem = progress.get("stem", "dubbed")
        input_path = progress.get("input_path")

        db.update_job_status(job_uuid, "running", progress={**progress, "step": "download"})

        from src.routes.video_dubbing import (
            _get_api_key,
            _download_dubbed_audio,
            _download_transcript,
            _transcript_to_subtitles,
            _apply_faststart,
            _embed_soft_subtitles,
        )

        api_key = _get_api_key()

        with ThreadPoolExecutor(max_workers=2) as pool:
            audio_future = pool.submit(_download_dubbed_audio, api_key, dubbing_id, target_lang)
            transcript_future = pool.submit(_download_transcript, api_key, dubbing_id, target_lang)
            raw_bytes = audio_future.result()
            transcript_json = transcript_future.result()

        subtitles = _transcript_to_subtitles(transcript_json) if transcript_json else {
            "srt": "", "vtt": "", "txt": "", "json": "[]",
        }

        if not is_video:
            result_path = save_result_file(job_uuid, ".mp3", raw_bytes)
            result_filename = f"{stem}_dubbed_{target_lang}.mp3"
        else:
            video_bytes = _apply_faststart(raw_bytes)
            if soft_subtitles and subtitles.get("srt"):
                try:
                    video_bytes = _embed_soft_subtitles(video_bytes, subtitles["srt"])
                except Exception as e:
                    logger.warning("Soft subtitle embed failed (non-fatal): {}", e)
            result_path = save_result_file(job_uuid, ".mp4", video_bytes)
            result_filename = f"{stem}_dubbed_{target_lang}.mp4"

        save_result_meta(job_uuid, subtitles)

        save_result_and_evict(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")

        if input_path:
            delete_file(input_path)

        logger.info("Dubbing download task {} completed: {}", job_uuid, result_filename)

    except Exception as e:
        logger.error("Dubbing download task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise
