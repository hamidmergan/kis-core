# backend/src/features/ai_assistant/routes/_citation_match.py
"""Deterministic lexical matcher that locates a claim's keyword inside a source's
position-bearing units (transcript segments or page-chunks). Language-agnostic,
no embeddings, identical on every model tier. See the citation-grounding design spec."""
from __future__ import annotations

import re
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
FUZZY_THRESHOLD = 0.5   # min token-containment for a fuzzy hit
UNIQUENESS_MARGIN = 0.15  # best must beat 2nd-best by this much


def _tokens(norm: str) -> set[str]:
    """Word tokens of already-normalised text. Splits on punctuation AND hyphens
    (so 'review-prozess' -> {'review','prozess'} and 'tabellenverzeichnis.' ->
    {'tabellenverzeichnis'}); keeps Unicode letters/digits incl. umlauts."""
    return set(re.findall(r"\w+", norm, flags=re.UNICODE))


def _stem_match(a: str, b: str) -> bool:
    """True if two normalized word tokens share a stem. Catches morphological variants
    a spoken-language summary paraphrases ('Schneeballprinzip' ↔ 'Schneeballsystem',
    'Qualität' ↔ 'Qualitätsprüfung'): exact, or a >=5-char common prefix, or the
    shorter token contained in the longer. Length-gated (both >=5) to avoid spurious
    matches on short function words. Language-agnostic — no wordlists."""
    if a == b:
        return True
    if len(a) < 5 or len(b) < 5:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if short in long:
        return True
    # Common-prefix stem: must be substantial in BOTH absolute length (>=6) and as a
    # fraction of the shorter token (>=60%). A short shared fragment like "schne"
    # ("schnell" vs "schneeball…") is NOT a shared stem — allowing it created false
    # ties that dropped the real chip.
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    return n >= 6 and n >= 0.6 * len(short)


def _containment(query_tokens: set[str], unit_tokens: set[str], *, stem: bool = False) -> float:
    """Fraction of the QUERY's tokens present in the unit. Robust to long units.
    With ``stem=True`` a query token also counts when it shares a stem with some unit
    token (``_stem_match``) — used for media, where the answer paraphrases speech."""
    if not query_tokens:
        return 0.0
    if not stem:
        return len(query_tokens & unit_tokens) / len(query_tokens)
    matched = sum(
        1 for q in query_tokens
        if q in unit_tokens or any(_stem_match(q, u) for u in unit_tokens)
    )
    return matched / len(query_tokens)


def _nearest(units: list[Unit], typed_pos: float | None) -> Unit:
    """Pick the unit whose position is closest to the model's typed position.
    Returns units[0] when typed_pos is None."""
    if typed_pos is None:
        return units[0]

    # Assumes a homogeneous position type: all units use start_time OR all use page.
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
    stem_match: bool = False,
) -> MatchResult:
    """Locate ``query`` in ``units``. typed_pos (a timestamp/page the model typed)
    is used ONLY as a tie-breaker among otherwise-equal hits, never as truth.
    ``stem_match`` enables stem-aware token comparison (media only) so a paraphrased
    spoken-language line still grounds; PDF keeps exact matching (default off)."""
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
        ((_containment(qtok, _tokens(u.normalized()), stem=stem_match), u) for u in units),
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
            chosen = _nearest(ties, typed_pos)
            chosen_score = next(s for s, u in scored if u is chosen)
            return MatchResult(chosen, chosen_score, "fuzzy")
        return MatchResult(None, best_score, "none")

    return MatchResult(scored[0][1], best_score, "fuzzy")


def _dedup_by_position(results: list[MatchResult], max_results: int) -> list[MatchResult]:
    """Keep at most ``max_results`` results, one per distinct position (page or
    start_time), best first. Two units on the same page collapse to the higher-scored
    one so a claim never yields two chips for the same page."""
    seen: set = set()
    out: list[MatchResult] = []
    for r in results:
        pos = r.unit.start_time if r.unit.start_time is not None else r.unit.page
        if pos in seen:
            continue
        seen.add(pos)
        out.append(r)
        if len(out) >= max_results:
            break
    return out


def match_query_multi(
    query: str,
    units: list[Unit],
    *,
    max_results: int = 2,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    margin: float = UNIQUENESS_MARGIN,
    stem_match: bool = False,
) -> list[MatchResult]:
    """Like ``match_query`` but, when the claim maps equally onto several positions,
    returns ONE result per near-tie position (best first, deduped, capped) instead of
    discarding the ambiguous match. Used by the uncited-line filler so a claim that
    genuinely lives on two pages (e.g. a glossary term spanning the Abkuerzungs-
    verzeichnis pages) shows a chip per page rather than none.

    A clear single winner returns a one-element list; nothing above threshold returns []."""
    nq = _norm_for_match(query)
    if not nq:
        return []

    # 1) exact normalized substring -> every such unit is a perfect (1.0) hit
    exact = [u for u in units if nq in u.normalized()]
    if exact:
        return _dedup_by_position([MatchResult(u, 1.0, "exact") for u in exact], max_results)

    # 2) token-containment fuzzy: keep the near-tie band (>= threshold AND within margin
    #    of the best). A confident winner has no peers in the band -> single result.
    qtok = _tokens(nq)
    scored = sorted(
        ((_containment(qtok, _tokens(u.normalized()), stem=stem_match), u) for u in units),
        key=lambda t: t[0],
        reverse=True,
    )
    if not scored or scored[0][0] < fuzzy_threshold:
        return []
    best = scored[0][0]
    near = [MatchResult(u, s, "fuzzy") for s, u in scored
            if s >= fuzzy_threshold and best - s < margin]
    return _dedup_by_position(near, max_results)
