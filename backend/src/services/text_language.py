"""The language of a text, read locally with langdetect instead of by a model call."""

from __future__ import annotations

from babel import Locale
from langdetect import DetectorFactory, LangDetectException, detect_langs

_SAMPLE_CHARS = 1500
# Below this the guess is noise, a file name or a page number is not a language.
_MIN_CHARS = 80
# A mixed or unclear sample is better described than named wrongly.
_MIN_PROB = 0.7
_NAMES = Locale("en").languages
DetectorFactory.seed = 0


def language_sample(text: str, sample_chars: int = _SAMPLE_CHARS) -> str:
    """An excerpt from the middle as a language sample, the edges mislead."""
    if len(text) <= sample_chars:
        return " ".join(text.split())
    mitte = len(text) // 2
    koerper = " ".join(text[max(0, mitte - sample_chars): mitte + sample_chars].split())
    if len(koerper) <= sample_chars:
        return koerper
    # Aus der Mitte heraus gekuerzt, sonst faellt genau die Mitte wieder weg.
    start = (len(koerper) - sample_chars) // 2
    return koerper[start:start + sample_chars]


def language_code(text: str) -> str | None:
    """The two-letter code of the text, None when it is too short or unclear."""
    probe = language_sample(text)
    if len(probe) < _MIN_CHARS:
        return None
    try:
        treffer = detect_langs(probe)[0]
    except LangDetectException:
        return None
    return treffer.lang.split("-")[0] if treffer.prob >= _MIN_PROB else None


def language_name(text: str) -> str | None:
    """The English name of the text's language, None when it is too short or unclear."""
    code = language_code(text)
    return _NAMES.get(code) if code else None
