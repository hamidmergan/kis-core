"""What the routes leave to the feature: the state of a conversation, its sentences, speech to text."""

import json
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from loguru import logger

from src.features.interpreter import repository as repo
from src.i18n import t

MAX_AUDIO_BYTES = 30 * 1024 * 1024
_AUDIO_SUFFIXES = {".webm", ".mp4", ".m4a", ".ogg", ".wav", ".mp3"}

# What a conversation may collect, spoken and typed together, roughly an hour of back and forth.
SESSION_CHAR_LIMIT = 20_000


def _turn_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "side": row["side"],
        "source": row["source"],
        "original": row["original"],
        "translation": row["translation"],
        "status": row["status"],
        "edited": bool(row["edited"]),
        "at": int(row["at"]),
    }


def state(session: dict) -> dict:
    return {
        "id": session["id"],
        "left_lang": session["left_lang"],
        "right_lang": session["right_lang"],
        "left_name": session["left_name"],
        "right_name": session["right_name"],
        "ended": session.get("ended_at") is not None,
        "created_at": session["created_at"].isoformat(),
        "turns": [_turn_out(row) for row in repo.list_turns(session["id"])],
    }


def summary(row: dict) -> dict:
    return {
        "id": row["id"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "ended": row.get("ended_at") is not None,
        "left_lang": row["left_lang"],
        "right_lang": row["right_lang"],
        "left_name": row["left_name"],
        "right_name": row["right_name"],
        "turn_count": int(row.get("turn_count") or 0),
        "first_original": row.get("first_original") or "",
        "first_translation": row.get("first_translation") or "",
        "first_side": row.get("first_side") or "left",
    }


def _chars_without(session_id: str, turn_id: str) -> int:
    """Everything said and typed so far, minus the sentence that is being rewritten."""
    return sum(len(row["original"]) for row in repo.list_turns(session_id) if row["id"] != turn_id)


def save_turn(session: dict, turn: dict, locale: str) -> dict:
    """A sentence typed away to nothing leaves the conversation again."""
    if session.get("ended_at") is not None:
        raise HTTPException(status_code=409, detail=t("interpreter.ended", locale))
    if not turn["original"].strip():
        repo.delete_turn(session["id"], turn["id"])
        return {"id": turn["id"], "deleted": True}
    if _chars_without(session["id"], turn["id"]) + len(turn["original"]) > SESSION_CHAR_LIMIT:
        raise HTTPException(status_code=409, detail=t("interpreter.full", locale))
    return _turn_out(repo.upsert_turn(session["id"], turn))


def _unwrap(raw: str) -> str:
    """Short clips come back from myLab as a JSON object, the client only cleans strings."""
    text = (raw or "").strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            return str(json.loads(text).get("text", "")).strip()
        except (json.JSONDecodeError, ValueError, AttributeError):
            return text
    return text


async def transcribe_upload(audio: UploadFile, provider_id: int | None, language: str | None, locale: str) -> str:
    """One window of a recording through Whisper, straight away, no job. The language spares Whisper the guess."""
    from src.dependencies import resolve_whisper_client
    from src.services.feature_router import FeatureNotConfigured

    suffix = Path(audio.filename or "window.webm").suffix.lower()
    if suffix not in _AUDIO_SUFFIXES:
        suffix = ".webm"
    fd, path = tempfile.mkstemp(prefix="interpreter_", suffix=suffix)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_AUDIO_BYTES:
                    raise HTTPException(status_code=413, detail=t("interpreter.audioTooLarge", locale))
                out.write(chunk)
        if size == 0:
            return ""
        try:
            client = resolve_whisper_client(provider_id)
        except FeatureNotConfigured as e:
            raise HTTPException(status_code=503, detail=t("interpreter.noStt", locale)) from e
        try:
            raw = await run_in_threadpool(client.transcribe, path, "text", language)
        except Exception as e:
            logger.warning("Interpreter transcription failed: {}", e)
            raise HTTPException(status_code=502, detail=t("interpreter.sttFailed", locale)) from e
        return _unwrap(raw)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
