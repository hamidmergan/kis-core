"""Segments a person pasted for a link-only source, plus the language they are in."""
from __future__ import annotations

import re

from loguru import logger

from src.services.subtitle_converter import vtt_to_segments
from src.storage import aia_provided_vtt_key, get_file

FALLBACK_LANGUAGE = "de"
_ISO_CODE = re.compile(r"^[a-z]{2}$")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_LANGUAGE_PROMPT = (
    "You get the beginning of a transcript. Answer with the ISO 639-1 code of its language only, "
    "two lowercase letters, nothing else."
)
_SAMPLE_CHARS = 600


def load_provided_segments(file_path: str) -> list[dict]:
    """Reads the stored VTT next to the source, empty when nothing is there."""
    try:
        raw = get_file(aia_provided_vtt_key(file_path)).decode("utf-8")
    except Exception as e:
        logger.warning("KI Tutor: provided transcript missing for {}: {}", file_path, e)
        return []
    return vtt_to_segments(raw)


def detect_language(segments: list[dict], client, model: str) -> str:
    """Asks the model for a two-letter code, anything else falls back to German."""
    sample = " ".join(s["text"] for s in segments)[:_SAMPLE_CHARS]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _LANGUAGE_PROMPT},
                {"role": "user", "content": sample},
            ],
            temperature=0,
        )
        answer = _THINK.sub("", response.choices[0].message.content or "").strip().lower()
    except Exception as e:
        logger.warning("KI Tutor: language detection failed: {}", e)
        return FALLBACK_LANGUAGE
    return answer if _ISO_CODE.match(answer) else FALLBACK_LANGUAGE
