"""Celery task: Video dubbing via ElevenLabs Dubbing API."""

import json
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import save_result_file, save_result_json


@celery_app.task(bind=True, name="video_dubbing.run")
def run_video_dubbing(
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
    """Dub a video/audio file using ElevenLabs Dubbing API."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "submit"})

        file_bytes = Path(input_path).read_bytes()
        ext = Path(filename).suffix.lower()

        # Import helpers from the route module (avoids code duplication)
        from src.routes.video_dubbing import (
            _get_api_key,
            _submit_dubbing_job,
            _poll_dubbing_job,
            _download_dubbed_audio,
            _download_transcript,
            _transcript_to_subtitles,
            _apply_faststart,
            _embed_soft_subtitles,
            VIDEO_DUBBING_VIDEO_EXTENSIONS,
        )
        from concurrent.futures import ThreadPoolExecutor

        is_video = ext in VIDEO_DUBBING_VIDEO_EXTENSIONS
        api_key = _get_api_key()
        stem = Path(filename).stem

        # Submit to ElevenLabs
        dubbing_id = _submit_dubbing_job(
            api_key, file_bytes, filename, ext,
            source_lang, target_lang, drop_background_audio, num_speakers,
        )
        logger.info("Dubbing job submitted: id='{}' for task {}", dubbing_id, job_uuid)

        db.update_job_status(job_uuid, "running", progress={"step": "dubbing", "dubbing_id": dubbing_id})

        # Poll until done
        _poll_dubbing_job(api_key, dubbing_id)

        db.update_job_status(job_uuid, "running", progress={"step": "download"})

        # Download audio + transcript in parallel
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

        # Save subtitle data as meta JSON alongside the result
        meta_path = Path(result_path).with_suffix(".meta.json")
        meta_path.write_text(json.dumps(subtitles), encoding="utf-8")

        db.update_job_result(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")

        # Clean up input file
        Path(input_path).unlink(missing_ok=True)

        logger.info("Video dubbing task {} completed: {}", job_uuid, result_filename)

    except Exception as e:
        logger.error("Video dubbing task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise
