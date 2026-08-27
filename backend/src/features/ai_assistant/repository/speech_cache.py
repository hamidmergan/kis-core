"""Shared pool for spoken example sentences, the audio lives in storage."""

import hashlib

from src import storage
from src.core.db.pool import get_connection

# How long an unheard audio file is kept.
SPEECH_CACHE_RETENTION_DAYS = 90


def normalize_sentence(sentence: str) -> str:
    """Prepares the sentence exactly as it reaches the provider."""
    return " ".join(line.strip() for line in (sentence or "").splitlines() if line.strip())


def fingerprint(sentence: str, provider_id: int, voice_id: str, speed: float,
                model: str = "") -> str:
    """The key of an audio file from sentence, provider, voice, speed and model."""
    roh = "\x00".join((
        normalize_sentence(sentence),
        str(provider_id),
        voice_id or "",
        f"{float(speed):.2f}",
        model or "",
    ))
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def get(key: str) -> bytes | None:
    """Fetches the audio for a fingerprint, or None and clears the dead row."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_speech_cache SET last_used_at = NOW()
                   WHERE fingerprint = %s
                   RETURNING fingerprint""",
                (key,),
            )
            row = cur.fetchone()
        # Refreshing needs a commit too, otherwise the cleanup throws away too much.
        conn.commit()
    if not row:
        return None

    audio = storage.get_speech_audio(key)
    if audio is None:
        _vergessen(key)
        return None
    return audio


def _vergessen(key: str) -> None:
    """Delete a row whose file no longer exists."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_speech_cache WHERE fingerprint = %s", (key,))
        conn.commit()


def put(key: str, audio: bytes) -> None:
    """Puts an audio file into the pool, the file first, then the row."""
    if not audio:
        return
    storage.save_speech_audio(key, audio)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_speech_cache (fingerprint, bytes)
                   VALUES (%s, %s)
                   ON CONFLICT (fingerprint) DO UPDATE SET last_used_at = NOW()""",
                (key, len(audio)),
            )
        conn.commit()


def prune(days: int = SPEECH_CACHE_RETENTION_DAYS) -> int:
    """Deletes audio nobody has listened to in a long time, files first, then rows."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT fingerprint FROM aia_speech_cache
                   WHERE last_used_at < NOW() - %s::interval""",
                (f"{int(days)} days",),
            )
            schluessel = [zeile[0] for zeile in cur.fetchall()]
    if not schluessel:
        return 0

    storage.delete_speech_audio(schluessel)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_speech_cache WHERE fingerprint = ANY(%s)",
                (schluessel,),
            )
        conn.commit()
    return len(schluessel)
