"""Titel-Normalisierung + Fuzzy-Matching für Schedule-Deduplication."""

from difflib import SequenceMatcher


def _norm_title(t: str) -> str:
    """Lower-case + whitespace/separator collapse. Language-agnostic."""
    raw = str(t or "").lower()
    for sep in "/:-_()[]{}|\"'":
        raw = raw.replace(sep, " ")
    return " ".join(raw.split())


def _token_overlap(a: str, b: str) -> float:
    """Fraction of shorter token set that also appears in the longer one.
    Handles stem-like matches by simple prefix comparison for 5+ char tokens.
    Digit-only tokens (years, day numbers, month numbers) are excluded — they
    carry no semantic signal about the event itself.
    Language-agnostic.
    """
    ta = set(t for t in _norm_title(a).split() if len(t) >= 3 and not t.isdigit())
    tb = set(t for t in _norm_title(b).split() if len(t) >= 3 and not t.isdigit())
    if not ta or not tb:
        return 0.0
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    hits = 0
    for t in small:
        if t in large:
            hits += 1
            continue
        # prefix match for stem variants: 'sprechstunde' matches 'sprechstunden'
        if len(t) >= 5 and any(
            (t.startswith(x[:5]) or x.startswith(t[:5])) for x in large
        ):
            hits += 1
    return hits / len(small)


def _fuzzy_same(a: str, b: str) -> bool:
    """Merge candidate and existing entry if titles are similar by EITHER
    character-level similarity (difflib >= 0.75) OR content-token overlap (>= 0.7).
    Both are language-agnostic.
    """
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if SequenceMatcher(None, na, nb).ratio() >= 0.75:
        return True
    if _token_overlap(a, b) >= 0.7:
        return True
    return False
