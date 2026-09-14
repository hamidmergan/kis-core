"""Groups date candidates so the model judges one of a kind instead of all of them."""

import re

# Only the words next to the date decide, the rest of the chunk is noise.
_WINDOW = 70
_DIGITS = re.compile(r"\d+")
_SPACE = re.compile(r"\s+")


def _key(cand: dict) -> tuple:
    """What makes two candidates the same question for the model."""
    context = cand.get("context") or ""
    raw = cand.get("date_raw") or ""
    pos = context.find(raw) if raw else -1
    if pos < 0:
        # Without the spot the middle is the best guess, the window is generous.
        pos, raw = len(context) // 2, ""
    window = context[max(0, pos - _WINDOW):pos + len(raw) + _WINDOW]
    window = _SPACE.sub(" ", _DIGITS.sub("#", window)).strip().lower()
    return (cand.get("date_iso"), tuple(cand.get("partial_date") or ()),
            bool(cand.get("is_tbd")), window)


def group_for_classification(candidates: list[dict]) -> tuple[list[dict], list[int]]:
    """The candidates worth asking about, plus each candidate's place in that list."""
    reps: list[dict] = []
    seen: dict[tuple, int] = {}
    mapping: list[int] = []
    for cand in candidates:
        key = _key(cand)
        if key not in seen:
            seen[key] = len(reps)
            reps.append(cand)
        mapping.append(seen[key])
    return reps, mapping
