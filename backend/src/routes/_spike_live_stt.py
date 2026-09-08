"""Throwaway spike: measures how live subtitles behave on top of the batch STT endpoint.

Delete this file, its HTML twin and the two lines in app.py once the numbers are in.
"""

import json
import os
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from loguru import logger

from src.services import feature_router

router = APIRouter(prefix="/spike", tags=["spike"])

_PAGE = Path(__file__).with_suffix(".html")
_MAX_WINDOW_BYTES = 30 * 1024 * 1024
_LAEUFE = Path("/tmp/spike_laeufe")


def _ms(start: float) -> int:
    """Elapsed milliseconds since a perf_counter mark."""
    return int((time.perf_counter() - start) * 1000)


def _unwrap(raw: str) -> str:
    """myLab answers short clips with a JSON object, clean_whisper_response only knows strings."""
    text = (raw or "").strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            return str(json.loads(text).get("text", "")).strip()
        except (json.JSONDecodeError, ValueError, AttributeError):
            return text
    return text


def _save_upload(upload: UploadFile, suffix: str) -> str:
    """Writes the upload to a temp file and returns its path."""
    fd, path = tempfile.mkstemp(prefix="spike_", suffix=suffix)
    size = 0
    with os.fdopen(fd, "wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > _MAX_WINDOW_BYTES:
                os.unlink(path)
                raise HTTPException(status_code=413, detail="window too large")
            out.write(chunk)
    if not size:
        os.unlink(path)
        raise HTTPException(status_code=400, detail="empty window")
    return path


def _transcribe(path: str) -> dict:
    """One STT call, split into client setup and the provider round trip."""
    t0 = time.perf_counter()
    try:
        binding = feature_router.resolve("stt")
        client = feature_router.make_whisper_client(binding)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"stt not configured: {e}") from e
    setup_ms = _ms(t0)

    t1 = time.perf_counter()
    try:
        text = client.transcribe(path, response_format="text")
    except Exception as e:
        logger.warning("Spike STT failed: {}", e)
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {
        "text": _unwrap(text),
        "setup_ms": setup_ms,
        "stt_ms": _ms(t1),
        "model": binding.model,
        "provider": binding.provider.get("name", ""),
    }


@router.get("/")
def page():
    """The measuring page, served here so the session cookie travels and CORS stays out."""
    if not _PAGE.exists():
        raise HTTPException(status_code=404, detail="spike page missing")
    return FileResponse(_PAGE, media_type="text/html")


@router.post("/stt")
def stt_window(audio: UploadFile = File(...)):
    """Transcribes one sliding window of audio."""
    path = _save_upload(audio, ".wav")
    try:
        return _transcribe(path)
    finally:
        os.unlink(path)


@router.post("/batch")
def stt_batch(audio: UploadFile = File(...)):
    """Transcribes a whole recording in one call, the quality yardstick for the live run."""
    suffix = Path(audio.filename or "input.wav").suffix or ".wav"
    path = _save_upload(audio, suffix)
    try:
        return _transcribe(path)
    finally:
        os.unlink(path)


@router.post("/translate")
def translate(text: str = Form(...), target: str = Form("Englisch")):
    """Translates a committed snippet, measured separately from the recognition."""
    schnipsel = text.strip()
    if not schnipsel:
        return {"text": "", "mt_ms": 0}

    t0 = time.perf_counter()
    try:
        binding = feature_router.resolve("transcript_translate")
        client = feature_router.make_llm_client(binding)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"transcript_translate not configured: {e}") from e
    setup_ms = _ms(t0)

    t1 = time.perf_counter()
    try:
        response = client._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=binding.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Übersetze den Text nach {target}. Gib ausschließlich die Übersetzung "
                        "zurück, ohne Einleitung, ohne Anführungszeichen. Der Text ist ein "
                        "Ausschnitt aus einer laufenden Vorlesung und kann mitten im Satz enden."
                    ),
                },
                {"role": "user", "content": schnipsel},
            ],
            **client.sampling(0.2),
        )
    except Exception as e:
        logger.warning("Spike translation failed: {}", e)
        raise HTTPException(status_code=502, detail=str(e)) from e

    inhalt = (response.choices[0].message.content or "").strip()
    return {
        "text": inhalt,
        "setup_ms": setup_ms,
        "mt_ms": _ms(t1),
        "model": binding.model,
        "provider": binding.provider.get("name", ""),
    }


@router.post("/lauf")
def lauf_sichern(lauf: dict = Body(...)):
    """Writes one finished run to disk so the numbers survive the browser tab."""
    _LAEUFE.mkdir(parents=True, exist_ok=True)
    name = time.strftime("%Y-%m-%d_%H-%M-%S") + ".json"
    ziel = _LAEUFE / name
    ziel.write_text(json.dumps(lauf, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Spike run saved: {}", ziel)
    return {"datei": str(ziel)}
