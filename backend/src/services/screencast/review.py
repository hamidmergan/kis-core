"""Helpers for the review step: find slides the translation left unchanged."""

import re

# Below this character count the comparison is not worthwhile.
_MIN_SIGNIFICANT_CHARS = 8

_WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _is_significant(text: str) -> bool:
    return sum(1 for c in text if c.isalnum()) >= _MIN_SIGNIFICANT_CHARS


def find_unchanged_slides(original_texts: list[str], translated_texts: list[str]) -> list[int]:
    """Slides whose text the translation left unchanged, as a hint."""
    flagged: list[int] = []
    for index, (original, translated) in enumerate(zip(original_texts, translated_texts)):
        normalized = _normalize(original)
        if not _is_significant(normalized):
            continue
        if normalized == _normalize(translated):
            flagged.append(index)
    return flagged
