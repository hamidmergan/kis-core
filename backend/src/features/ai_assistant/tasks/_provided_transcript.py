"""Segments a person pasted for a link-only source, plus the language they are in."""
from __future__ import annotations

from loguru import logger

from src.services.subtitle_converter import vtt_to_segments
from src.services.text_language import language_code
from src.storage import aia_provided_vtt_key, get_file

FALLBACK_LANGUAGE = "de"


def load_provided_segments(file_path: str) -> list[dict]:
    """Reads the stored VTT next to the source, empty when nothing is there."""
    try:
        raw = get_file(aia_provided_vtt_key(file_path)).decode("utf-8")
    except Exception as e:
        logger.warning("KI Tutor: provided transcript missing for {}: {}", file_path, e)
        return []
    return vtt_to_segments(raw)


def detect_language(segments: list[dict]) -> str:
    """The two-letter code of the transcript, read locally, unclear text falls back to German."""
    return language_code(" ".join(s["text"] for s in segments)) or FALLBACK_LANGUAGE
