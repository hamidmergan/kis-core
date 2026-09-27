"""Which queue a service job starts in, decided by its size, so long work never blocks short work."""
from __future__ import annotations

from loguru import logger

from src.limits import LONG_QUEUE_MEDIA_SECONDS, LONG_QUEUE_TRANSLATE_CHARS

# Rough characters per PDF page, a PDF's text is only read in the worker.
_CHARS_PER_PAGE = 3_000


# In the long queue big jobs come last, outlines and scripts of a few minutes pass them.
_LONG = {"queue": "long", "priority": 9}
_SHORT = {"queue": "general"}


def translate_route(chars: int | None = None, pages: int | None = None) -> dict:
    """The long queue for texts above the limit, an unknown size stays short."""
    umfang = chars if chars is not None else (pages * _CHARS_PER_PAGE if pages else None)
    return dict(_LONG if umfang is not None and umfang > LONG_QUEUE_TRANSLATE_CHARS else _SHORT)


def transcribe_route(seconds: float | None) -> dict:
    """The long queue for recordings above the limit, an unknown length stays short."""
    return dict(_LONG if seconds is not None and seconds > LONG_QUEUE_MEDIA_SECONDS else _SHORT)


def media_seconds(path: str) -> float | None:
    """Length of a recording, None when ffprobe cannot read it."""
    from src.services.openai_compat_llm._chunking import get_audio_duration

    try:
        return get_audio_duration(path)
    except Exception as e:  # noqa: BLE001 - an unreadable length only means the short queue
        logger.warning("Länge der Aufnahme nicht lesbar: {}", e)
        return None
