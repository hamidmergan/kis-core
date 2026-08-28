"""Recognises a refusal answer by its distance to the model sentences."""

import math


# Distance threshold below which a line counts as a refusal and gets no chip.
_REFUSAL_MAX_DIST = 0.60


def _cos_dist(a, b) -> float:
    """Cosine distance of two equally long vectors, 1.0 on degenerate input."""
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 1.0
    return 1.0 - dot / (math.sqrt(na) * math.sqrt(nb))


def _refusal_lines(cands: list[str], vec_by_line: dict, sentinel_vecs: list,
                   max_dist: float = _REFUSAL_MAX_DIST) -> set:
    """Which candidate lines are a refusal, measured by distance to the model sentence."""
    if not sentinel_vecs:
        return set()
    flagged: set = set()
    for ln in cands:
        v = vec_by_line.get(ln)
        if v is None:
            continue
        if any(_cos_dist(v, sv) <= max_dist for sv in sentinel_vecs):
            flagged.add(ln)
    return flagged


def is_refusal_answer(text: str, embed_fn, sentinels: list[str],
                      max_dist: float = _REFUSAL_MAX_DIST) -> bool:
    """True when the whole answer is a refusal."""
    cleaned = (text or "").strip()
    if not cleaned or not sentinels:
        return False
    try:
        vecs = embed_fn([cleaned] + sentinels)
    except Exception:
        return False
    if len(vecs) != 1 + len(sentinels):
        return False
    answer_vec, sentinel_vecs = vecs[0], vecs[1:]
    return any(_cos_dist(answer_vec, sv) <= max_dist for sv in sentinel_vecs)
