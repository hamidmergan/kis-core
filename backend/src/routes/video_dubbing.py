"""Video dubbing route: uses ElevenLabs Dubbing API for synchronized dubbing."""

import subprocess
import time
import tempfile
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from src.dependencies import get_settings
from src.utils.file_validation import (
    MAX_TRANSCRIPTION_BYTES,
    VIDEO_DUBBING_VIDEO_EXTENSIONS,
)

router = APIRouter(tags=["video-dubbing"])

_ELEVENLABS_DUBBING_URL = "https://api.elevenlabs.io/v1/dubbing"
_POLL_INTERVAL = 10   # seconds between status checks
_MAX_ATTEMPTS = 120   # max ~20 minutes


def _validate_upload(filename: str | None, allowed: dict, label: str) -> str:
    """Validate filename and return its lowercase extension."""
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


@router.post("/video-dubbing")
async def video_dubbing(
    request: Request,
    video: UploadFile = File(...),
    source_lang: str = Form("de"),
    target_lang: str = Form("en"),
    drop_background_audio: bool = Form(False),
    num_speakers: int = Form(0),
):
    """Dub a video using ElevenLabs Dubbing API.

    Args:
        video: Video file to dub.
        source_lang: Source language code (e.g. 'de', 'en'). Defaults to 'de'.
        target_lang: Target language code (e.g. 'en', 'de'). Defaults to 'en'.
        drop_background_audio: Remove background audio for cleaner dub.
        num_speakers: Number of speakers (0 = auto-detect).
    """
    # Validate file
    video_ext = _validate_upload(video.filename, VIDEO_DUBBING_VIDEO_EXTENSIONS, "Video")

    # Validate size
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_TRANSCRIPTION_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 500 MB)")

    video_bytes = await video.read()
    if not video_bytes:
        raise HTTPException(status_code=400, detail="Video ist leer")

    api_key = _get_api_key()
    stem = Path(video.filename).stem  # type: ignore[arg-type]

    # ── Step 1: Submit dubbing job ──────────────────────────────────────────
    logger.info(
        "Video dubbing: submitting '{}' ({} → {})",
        video.filename, source_lang, target_lang,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_video = Path(tmpdir) / f"input{video_ext}"
        tmp_video.write_bytes(video_bytes)

        with httpx.Client(timeout=120.0) as client:
            with open(tmp_video, "rb") as f:
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
                    files={"file": (video.filename, f, "video/mp4")},
                )

    if response.status_code != 200:
        logger.error("ElevenLabs dubbing submit failed: {}", response.text[:300])
        raise HTTPException(
            status_code=502,
            detail=f"ElevenLabs Fehler ({response.status_code}): {response.text[:200]}",
        )

    dubbing_id: str = response.json()["dubbing_id"]
    expected_duration: float = response.json().get("expected_duration_sec", 0)
    logger.info(
        "Dubbing job submitted: id='{}', expected={:.0f}s",
        dubbing_id, expected_duration,
    )

    # ── Step 2: Poll until complete ─────────────────────────────────────────
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
                break
            elif status in ("failed", "error"):
                error_msg = status_data.get("error_message", "Unknown error")
                logger.error("Dubbing failed: {}", error_msg)
                raise HTTPException(status_code=502, detail=f"Dubbing fehlgeschlagen: {error_msg}")
        else:
            raise HTTPException(status_code=504, detail="Dubbing Timeout – bitte später erneut versuchen")

    # ── Step 3: Download dubbed video ───────────────────────────────────────
    logger.info("Dubbing complete, downloading result for id='{}'", dubbing_id)

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

    # ── Step 4: Fix moov atom position with faststart ───────────────────
    raw_bytes = download_resp.content
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
        logger.info("Running faststart fix: {}", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning("faststart fix failed, returning raw file: {}", result.stderr[:200])
            output_bytes = raw_bytes
        else:
            output_bytes = fixed_path.read_bytes()

    output_name = f"{stem}_dubbed_{target_lang}.mp4"
    encoded_name = quote(output_name, safe="")
    logger.info("Video dubbing complete: '{}', size={} bytes", output_name, len(output_bytes))

    return StreamingResponse(
        iter([output_bytes]),
        media_type="video/mp4",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{encoded_name}"; '
                f"filename*=UTF-8''{encoded_name}"
            ),
            "Content-Length": str(len(output_bytes)),
            "Accept-Ranges": "bytes",
        },
    )
