# backend/src/features/ai_assistant/routes/_citation_match.py
"""Deterministic lexical matcher that locates a claim's keyword inside a source's
position-bearing units (transcript segments or page-chunks). Language-agnostic,
no embeddings, identical on every model tier. See the citation-grounding design spec."""
from __future__ import annotations

from dataclasses import dataclass

from ._helpers import _norm_for_match  # existing normalizer used by the resolver


@dataclass
class Unit:
    """One position-bearing piece of a source.

    Exactly one of (page) / (start_time) is set: page for PDF/doc/pptx, start_time
    for audio/video segments. ``norm_text`` is filled lazily from ``raw_text``.
    """
    page: int | None
    start_time: float | None
    end_time: float | None
    raw_text: str
    norm_text: str | None = None

    def normalized(self) -> str:
        if self.norm_text is None:
            self.norm_text = _norm_for_match(self.raw_text)
        return self.norm_text


@dataclass
class MatchResult:
    unit: Unit | None
    score: float
    match_type: str  # "exact" | "fuzzy" | "none"


# Calibrated later against the audit eval; these are starting values.
FUZZY_THRESHOLD = 0.6   # min token-containment for a fuzzy hit
UNIQUENESS_MARGIN = 0.15  # best must beat 2nd-best by this much


def _tokens(norm: str) -> set[str]:
    return set(norm.split())


def _containment(query_tokens: set[str], unit_tokens: set[str]) -> float:
    """Fraction of the QUERY's tokens present in the unit. Robust to long units."""
    if not query_tokens:
        return 0.0
    return len(query_tokens & unit_tokens) / len(query_tokens)


def _nearest(units: list[Unit], typed_pos: float | None) -> Unit:
    """Pick the unit whose position is closest to the model's typed position."""
    if typed_pos is None:
        return units[0]

    def dist(u: Unit) -> float:
        pos = u.start_time if u.start_time is not None else (u.page or 0)
        return abs(pos - typed_pos)

    return min(units, key=dist)


def match_query(
    query: str,
    units: list[Unit],
    *,
    typed_pos: float | None = None,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    margin: float = UNIQUENESS_MARGIN,
) -> MatchResult:
    """Locate ``query`` in ``units``. typed_pos (a timestamp/page the model typed)
    is used ONLY as a tie-breaker among otherwise-equal hits, never as truth."""
    nq = _norm_for_match(query)
    if not nq:
        return MatchResult(None, 0.0, "none")

    # 1) exact normalized substring
    exact = [u for u in units if nq in u.normalized()]
    if exact:
        return MatchResult(_nearest(exact, typed_pos), 1.0, "exact")

    # 2) token-containment fuzzy
    qtok = _tokens(nq)
    scored = sorted(
        ((_containment(qtok, _tokens(u.normalized())), u) for u in units),
        key=lambda t: t[0],
        reverse=True,
    )
    if not scored or scored[0][0] < fuzzy_threshold:
        return MatchResult(None, scored[0][0] if scored else 0.0, "none")

    best_score = scored[0][0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if best_score - second < margin:
        # near-tie among different units -> not confident enough
        ties = [u for s, u in scored if best_score - s < margin]
        if typed_pos is not None:
            return MatchResult(_nearest(ties, typed_pos), best_score, "fuzzy")
        return MatchResult(None, best_score, "none")

    return MatchResult(scored[0][1], best_score, "fuzzy")
