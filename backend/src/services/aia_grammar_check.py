"""Checks a free-text answer by comparison, without a model call."""

import re
import unicodedata

VERDICT_CORRECT = "correct"
VERDICT_CLOSE = "close"
VERDICT_WRONG = "wrong"

# From this word overlap on an answer counts as close on the fallback path.
_CLOSE_RATIO = 0.72

# Parentheticals are optional and are dropped before the comparison.
_PARENS_RE = re.compile(r"\([^)]*\)")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Comparison form: lowercased, without parentheticals, without punctuation."""
    if not text:
        return ""
    cleaned = _PARENS_RE.sub(" ", text)
    # Unicode category P* is all punctuation, in every language.
    cleaned = "".join(
        " " if unicodedata.category(ch).startswith("P") else ch
        for ch in cleaned
    )
    return _WS_RE.sub(" ", cleaned).strip().casefold()


def is_exact_match(given: str, expected: str) -> bool:
    """True when the normalised answer matches the model solution."""
    normalized = normalize(given)
    return bool(normalized) and normalized == normalize(expected)


def overlap_ratio(given: str, expected: str) -> float:
    """Share of shared words, multiplicity included, from 0.0 to 1.0."""
    a = normalize(given).split()
    b = normalize(expected).split()
    if not a or not b:
        return 0.0
    pool = list(b)
    hits = 0
    for word in a:
        if word in pool:
            pool.remove(word)
            hits += 1
    return hits / max(len(a), len(b))


def mark_answer(given: str, expected: str, accepts=()) -> str:
    """Verdict on an answer: correct, close or wrong."""
    candidates = [expected, *accepts]
    if any(is_exact_match(given, c) for c in candidates):
        return VERDICT_CORRECT
    best = max(overlap_ratio(given, c) for c in candidates)
    return VERDICT_CLOSE if best >= _CLOSE_RATIO else VERDICT_WRONG


__all__ = [
    "VERDICT_CORRECT", "VERDICT_CLOSE", "VERDICT_WRONG",
    "normalize", "is_exact_match", "overlap_ratio", "mark_answer",
]
