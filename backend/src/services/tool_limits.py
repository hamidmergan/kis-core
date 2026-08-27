"""Limits of the global tools, read at runtime instead of at startup."""

from loguru import logger

from src import database as db
from src.limits import (
    MAX_AUDIO_SEC,
    MAX_QUEUED_SCREENCAST_JOBS,
    MAX_RESULT_FILES,
    MAX_SCREENCAST_SLIDES,
    MAX_UPLOAD_BYTES,
)

_BYTES_PER_MB = 1024 * 1024

# Only these two may be unlimited.
UNBEGRENZT = -1
_DARF_UNBEGRENZT = frozenset({"results_kept_per_user", "screencast_max_open_jobs"})


def _zahl(key: str, vorgabe: int) -> int:
    """Reads an entry, unusable values fall back to the default."""
    roh = db.get_setting(key, "")
    if not roh:
        return vorgabe
    try:
        wert = int(str(roh).strip())
    except (TypeError, ValueError):
        logger.warning("Einstellung {} ist keine Zahl ({!r}), nehme {}", key, roh, vorgabe)
        return vorgabe
    if wert == UNBEGRENZT and key in _DARF_UNBEGRENZT:
        return UNBEGRENZT
    if wert < 1:
        logger.warning("Einstellung {} ist {}, nehme {}", key, wert, vorgabe)
        return vorgabe
    return wert


def max_screencast_slides() -> int:
    """Folien je Screencast."""
    return _zahl("screencast_max_slides", MAX_SCREENCAST_SLIDES)


def max_transcription_seconds() -> int:
    """Length of a recording, the admin area shows minutes, the code uses seconds."""
    minuten = _zahl("transcription_max_minutes", MAX_AUDIO_SEC // 60)
    return minuten * 60


def max_upload_bytes() -> int:
    """Size of an uploaded file, the admin area shows MB."""
    return _zahl("upload_max_mb", MAX_UPLOAD_BYTES // _BYTES_PER_MB) * _BYTES_PER_MB


def results_kept_per_user() -> int:
    """Retained jobs per user, -1 means unlimited."""
    return _zahl("results_kept_per_user", MAX_RESULT_FILES)


def max_open_screencast_jobs() -> int:
    """Open screencast jobs per user, ``-1`` means unlimited."""
    return _zahl("screencast_max_open_jobs", MAX_QUEUED_SCREENCAST_JOBS)
