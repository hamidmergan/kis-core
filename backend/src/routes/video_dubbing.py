"""Video dubbing route: uses ElevenLabs Dubbing API for synchronized dubbing.

Supported input formats:
  - MP4 video → returns dubbed MP4 (with faststart)
  - MP3 audio → returns dubbed MP3

Returns a single JSON response with base64-encoded media and subtitle formats
(SRT, VTT, TXT, JSON) derived from the ElevenLabs transcript endpoint.
"""

import base64
import json as json_module
import subprocess
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from src.dependencies import get_settings, get_current_user
from src import database as db
from src.storage import save_queue_file
from src.services.subtitle_converter import (
    segments_to_srt,
    segments_to_vtt,
    segments_to_txt,
    words_to_segments,
)
from src.utils.file_validation import (
    MAX_TRANSCRIPTION_BYTES,
    VIDEO_DUBBING_AUDIO_EXTENSIONS,
    VIDEO_DUBBING_VIDEO_EXTENSIONS,
)

router = APIRouter(tags=["video-dubbing"])

_ELEVENLABS_DUBBING_URL = "https://api.elevenlabs.io/v1/dubbing"
_POLL_INTERVAL = 10   # seconds between status checks
_MAX_ATTEMPTS = 120   # max ~20 minutes

_ALL_EXTENSIONS = {**VIDEO_DUBBING_VIDEO_EXTENSIONS, **VIDEO_DUBBING_AUDIO_EXTENSIONS}


def _validate_upload(filename: str | None, allowed: dict, label: str) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail=f"{label}: filename missing")
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"{label}: only {', '.join(allowed.keys())} allowed",
        )
    return ext


def _get_api_key() -> str:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=500, detail="ElevenLabs API Key fehlt")
    return settings.elevenlabs_api_key


def _submit_dubbing_job(
    api_key: str,
    file_bytes: bytes,
    filename: str,
    ext: str,
    source_lang: str,
    target_lang: str,
    drop_background_audio: bool,
    num_speakers: int,
) -> str:
    """Submit file to ElevenLabs Dubbing API and return dubbing_id."""
    stem = Path(filename).stem
    mime = _ALL_EXTENSIONS.get(ext, "application/octet-stream")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / f"input{ext}"
        tmp_file.write_bytes(file_bytes)

        with httpx.Client(timeout=120.0) as client:
            with open(tmp_file, "rb") as f:
                response = client.post(
                    _ELEVENLABS_DUBBING_URL,
                    headers={"xi-api-key": api_key},
                    data={
                        "name": stem,
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "num_speakers": str(num_speakers),
                        "drop_background_audio": str(drop_background_audio).lower(),
                        "watermark": "false",
                        "highest_resolution": "false",
                    },
                    files={"file": (filename, f, mime)},
                )

    if response.status_code != 200:
        logger.error("ElevenLabs dubbing submit failed: {}", response.text[:300])
        raise HTTPException(
            status_code=502,
            detail=f"ElevenLabs Fehler ({response.status_code}): {response.text[:200]}",
        )

    return response.json()["dubbing_id"]


def _poll_dubbing_job(api_key: str, dubbing_id: str) -> None:
    """Poll until dubbing job is complete or raise HTTPException."""
    with httpx.Client(timeout=30.0) as client:
        for attempt in range(_MAX_ATTEMPTS):
            time.sleep(_POLL_INTERVAL)
            status_resp = client.get(
                f"{_ELEVENLABS_DUBBING_URL}/{dubbing_id}",
                headers={"xi-api-key": api_key},
            )
            if status_resp.status_code != 200:
                logger.warning("Status check failed (attempt {}): {}", attempt + 1, status_resp.text[:200])
                continue

            status_data = status_resp.json()
            status = status_data.get("status", "")
            logger.info("Dubbing status (attempt {}): '{}'", attempt + 1, status)

            if status == "dubbed":
                return
            elif status in ("failed", "error"):
                error_msg = status_data.get("error_message", "Unknown error")
                logger.error("Dubbing failed: {}", error_msg)
                raise HTTPException(status_code=502, detail=f"Dubbing fehlgeschlagen: {error_msg}")

    raise HTTPException(status_code=504, detail="Dubbing Timeout – bitte später erneut versuchen")


def _check_dubbing_status_once(api_key: str, dubbing_id: str) -> str:
    """Single status check — returns ElevenLabs status string (e.g. 'dubbed', 'dubbing', 'failed')."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            f"{_ELEVENLABS_DUBBING_URL}/{dubbing_id}",
            headers={"xi-api-key": api_key},
        )
    if resp.status_code != 200:
        logger.warning("Status check failed for {}: {}", dubbing_id, resp.text[:200])
        return "pending"
    return resp.json().get("status", "pending")


def _download_dubbed_audio(api_key: str, dubbing_id: str, target_lang: str) -> bytes:
    """Download the dubbed audio/video from ElevenLabs."""
    with httpx.Client(timeout=300.0) as client:
        download_resp = client.get(
            f"{_ELEVENLABS_DUBBING_URL}/{dubbing_id}/audio/{target_lang}",
            headers={"xi-api-key": api_key},
        )

    if download_resp.status_code != 200:
        logger.error("Download failed: {}", download_resp.text[:300])
        raise HTTPException(
            status_code=502,
            detail=f"Download fehlgeschlagen ({download_resp.status_code})",
        )

    return download_resp.content


def _download_transcript(api_key: str, dubbing_id: str, target_lang: str) -> dict:
    """Download the word-level JSON transcript from ElevenLabs."""
    url = f"{_ELEVENLABS_DUBBING_URL}/{dubbing_id}/transcript/{target_lang}"
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(
            url,
            params={"format_type": "json"},
            headers={"xi-api-key": api_key},
        )

    if resp.status_code != 200:
        logger.warning("Transcript download failed ({}): {}", resp.status_code, resp.text[:300])
        return {}

    return resp.json()


def _transcript_to_subtitles(transcript_json: dict) -> dict[str, str]:
    """Convert ElevenLabs transcript JSON to SRT/VTT/TXT/JSON subtitle strings.

    The transcript contains a ``words`` list with entries like
    ``{"text": "hello", "start": 0.5, "end": 0.8, "type": "word"}``.
    We normalise ``text`` → ``word`` and filter for ``type == "word"``.
    """
    raw_words = transcript_json.get("words", [])
    words = [
        {"word": w["text"], "start": w["start"], "end": w["end"]}
        for w in raw_words
        if w.get("type") == "word"
    ]

    segments = words_to_segments(words)

    return {
        "srt": segments_to_srt(segments),
        "vtt": segments_to_vtt(segments),
        "txt": segments_to_txt(segments),
        "json": json_module.dumps(segments, ensure_ascii=False),
    }


def _apply_faststart(raw_bytes: bytes) -> bytes:
    """Apply ffmpeg faststart fix to MP4 for browser streaming."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        raw_path = tmp / "raw.mp4"
        fixed_path = tmp / "fixed.mp4"
        raw_path.write_bytes(raw_bytes)

        cmd = [
            "ffmpeg", "-y", "-i", str(raw_path),
            "-c", "copy", "-movflags", "+faststart",
            str(fixed_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning("faststart fix failed, returning raw: {}", result.stderr[:200])
            return raw_bytes
        return fixed_path.read_bytes()


def _embed_soft_subtitles(video_bytes: bytes, srt_text: str) -> bytes:
    """Embed SRT as a soft subtitle track into MP4 using ffmpeg."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        video_path = tmp / "input.mp4"
        srt_path = tmp / "subs.srt"
        out_path = tmp / "output.mp4"

        video_path.write_bytes(video_bytes)
        srt_path.write_text(srt_text, encoding="utf-8")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(srt_path),
            "-c", "copy",
            "-c:s", "mov_text",
            "-movflags", "+faststart",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning("Subtitle embed failed, returning video without subs: {}", result.stderr[:300])
            return video_bytes
        return out_path.read_bytes()


@router.post("/video-dubbing")
async def video_dubbing(
    request: Request,
    file: UploadFile = File(...),
    source_lang: str = Form("de"),
    target_lang: str = Form("en"),
    drop_background_audio: bool = Form(False),
    num_speakers: int = Form(0),
    soft_subtitles: bool = Form(False),
    current_user: dict = Depends(get_current_user),
):
    """Queue a video dubbing job using ElevenLabs Dubbing API.

    Returns ``{ job_uuid }`` immediately. Poll ``GET /jobs/{job_uuid}`` for status.
    On success the result contains ``download_url`` (dubbed media) and subtitle
    data (srt/vtt/txt/json) in the ``meta`` field.
    """
    ext = _validate_upload(file.filename, _ALL_EXTENSIONS, "Datei")

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 500 MB)")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Datei ist leer")

    # Validate API key before queuing
    _get_api_key()

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    input_path = save_queue_file(job_uuid, ext, file_bytes)
    db.create_job(job_uuid, user_id, "video_dubbing", file.filename or f"input{ext}", input_path)

    from src.tasks.video_dubbing_tasks import submit_dubbing
    task = submit_dubbing.apply_async(args=[
        job_uuid,
        input_path,
        file.filename or f"input{ext}",
        source_lang,
        target_lang,
        drop_background_audio,
        num_speakers,
        soft_subtitles,
    ])
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("Video dubbing job queued: job_uuid={}, file={} ({} → {})", job_uuid, file.filename, source_lang, target_lang)
    return JSONResponse(content={"job_uuid": job_uuid})
