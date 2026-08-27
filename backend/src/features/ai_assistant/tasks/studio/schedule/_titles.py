"""Title normalization plus fuzzy matching for schedule deduplication."""

from difflib import SequenceMatcher


def _find_merge_target(entries: list[dict], due_date, precision: str,
                       title: str, ref: dict, end_date=None) -> dict | None:
    """The entry this hit belongs to, or None for a new one."""
    same_title = _fuzzy_same_undated if due_date is None else _fuzzy_same
    for e in entries:
        if e.get("due_date") != due_date:
            continue
        if e.get("end_date") != end_date:
            continue
        if (e.get("date_precision") or "day") != (precision or "day"):
            continue
        if same_title(title, e.get("title") or ""):
            return e
        if due_date is None and _same_source_text(ref.get("raw_quote") or "",
                                                  e.get("source_refs") or []):
            return e
    return None


def _norm_quote(text: str) -> str:
    """Comparison form of a hit: lowercased, one space between the words."""
    return " ".join(str(text or "").lower().split())


def _same_source_text(quote: str, refs: list[dict]) -> bool:
    """Is exactly this wording already attached to an entry?"""
    key = _norm_quote(quote)
    if not key:
        return False
    return any(_norm_quote(r.get("raw_quote") or "") == key for r in refs)


def _norm_title(t: str) -> str:
    """Lower-case + whitespace/separator collapse. Language-agnostic."""
    raw = str(t or "").lower()
    for sep in "/:-_()[]{}|\"'":
        raw = raw.replace(sep, " ")
    return " ".join(raw.split())


def _token_overlap(a: str, b: str) -> float:
    """Word overlap of the shorter title in the longer one, numbers do not count."""
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


def _fuzzy_same_undated(a: str, b: str) -> bool:
    """Stricter character comparison for entries without a date."""
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    return SequenceMatcher(None, na, nb).ratio() >= 0.75


def _fuzzy_same(a: str, b: str) -> bool:
    """Merges two entries on similar characters or similar words."""
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if SequenceMatcher(None, na, nb).ratio() >= 0.75:
        return True
    if _token_overlap(a, b) >= 0.7:
        return True
    return False
