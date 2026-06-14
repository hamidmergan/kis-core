"""Shared, tool-facing post-hoc attribution.

The chat re-grounds each answer line against pgvector and attaches a nav-only chip
(closest retrieved chunk within a distance gate, page for PDFs / timestamp for media,
or NO chip when nothing is close enough). The studio tools (flashcards, quiz, …) used
to guess pages with their own lexical heuristics instead. This module lets a tool reuse
the EXACT same selector, but returns STRUCTURED chips (dicts) for the item's ``sources``
JSON instead of inline markdown chip strings.

One logic source: the distance gate (``_GENERIC_ATTRIB_MAX_DIST`` = 0.6) and the selector
(``_pick_attribution``) are imported from the chat helper, not re-implemented.

Note: a looser tool gate (0.66) was tried to catch a few borderline-correct pages a card
states only tersely, but it was reverted — the gate cannot help here. The closest WRONG
page (a topically-adjacent one) sat at 0.626, i.e. NEARER than the genuinely-correct
borderline pages at 0.631-0.653, so any gate that admits the good ones also admits the bad
one. 0.6 stays: no fabricated page, at the cost of leaving the rare terse case chip-less.
"""

from src.features.ai_assistant.routes._helpers import (
    _pick_attribution,
    _is_seen,
    _GENERIC_ATTRIB_MAX_DIST,
    _MULTI_CHIP_MAX_DELTA,
    _MAX_CHIPS_PER_LINE,
)


def _chip_key(chip: dict) -> tuple:
    """Identity of a nav chip: source + page (PDF) or timestamp (media)."""
    return (chip["source_label"], chip["page_number"], chip["start_time"])


def _chip_from_chunk(chunk: dict, label: str) -> dict:
    """Nav-only structured chip. Media (has start_time) cites its timestamp and carries
    no page; a PDF cites its page. Mirrors the chat's ``_attribution_chip`` start-time-first
    rule so audio/video never gets a bogus "S. <segment-index>"."""
    st = chunk.get("start_time")
    if st is not None:
        return {"source_label": label, "page_number": None, "start_time": st}
    return {"source_label": label, "page_number": chunk.get("page_number"), "start_time": None}


def attribute_claims(
    claims: list[str],
    source_id_to_label: dict[int, str],
    *,
    multi: bool = False,
    workspace_id: int | None = None,
    source_ids: list[int] | None = None,
    seen_pages_by_source: dict | None = None,
    embed_fn=None,
    search_fn=None,
) -> list[list[dict]]:
    """Attribute a batch of claim texts to nav-only source chips, one chip-list per claim.

    Embeds ALL claims in ONE call (``embed_fn``), then per claim runs hybrid search
    (``search_fn``) scoped to ``source_ids`` and selects chips via :func:`chips_for_claim`.
    ``seen_pages_by_source`` (optional) clamps chips to pages actually shown to the LLM, like
    the chat's seen-check. ``embed_fn``/``search_fn`` are injectable for testing; in production
    they default to the shared embedding provider and ``db.hybrid_search_chunks`` (fuzzy OFF)."""
    if not claims:
        return []

    if embed_fn is None:
        from src.services.aia_embeddings import get_embedding_provider
        embed_fn = get_embedding_provider().embed
    if search_fn is None:
        from src import database as db

        def search_fn(text, vec):
            return db.hybrid_search_chunks(workspace_id, text, vec,
                                           source_ids=source_ids, limit=10, fuzzy=False)

    try:
        vecs = embed_fn(claims)
    except Exception as e:
        from loguru import logger
        logger.warning("aia attribution: batch embed failed, no chips attached: {}", e)
        return [[] for _ in claims]

    out: list[list[dict]] = []
    for claim, vec in zip(claims, vecs):
        try:
            hits = search_fn(claim, vec)
        except Exception as e:
            from loguru import logger
            logger.warning("aia attribution: search failed for a claim, no chip: {}", e)
            hits = []
        out.append(chips_for_claim(hits, source_id_to_label, multi=multi,
                                   seen_pages_by_source=seen_pages_by_source))
    return out


def chips_for_claim(
    hits: list[dict],
    source_id_to_label: dict[int, str],
    *,
    multi: bool = False,
    max_distance: float = _GENERIC_ATTRIB_MAX_DIST,
    seen_pages_by_source: dict | None = None,
) -> list[dict]:
    """Turn ranked search hits for one claim into nav-only structured source chips.

    With ``multi=True`` a claim genuinely drawn from several passages also cites the
    co-sources that sit CLOSE to the best one (within ``_MULTI_CHIP_MAX_DELTA``), deduped
    by source/page and capped at ``_MAX_CHIPS_PER_LINE`` — the same relative gate the chat
    uses, so a clearly-best single source never collects on-topic near-misses.

    ``seen_pages_by_source`` (optional) restricts hits to source/pages the LLM was actually
    shown (chat-style seen-check) BEFORE selecting — so a chip can never point at a page that
    was not in the generation context.

    Returns ``[]`` when nothing lands within the distance gate (no fabricated source)."""
    if seen_pages_by_source is not None:
        hits = [h for h in hits if _is_seen(h, seen_pages_by_source)]
    best = _pick_attribution(hits, max_distance)
    if best is None:
        return []
    best_label = source_id_to_label.get(best["source_id"], "")
    chips = [_chip_from_chunk(best, best_label)]
    if not multi:
        return chips

    seen = {_chip_key(chips[0])}
    best_dist = best["vec_distance"]
    for h in sorted(hits, key=lambda x: x["vec_distance"]):
        if len(chips) >= _MAX_CHIPS_PER_LINE:
            break
        d = h.get("vec_distance")
        if d is None or d > max_distance or d - best_dist > _MULTI_CHIP_MAX_DELTA:
            continue
        chip = _chip_from_chunk(h, source_id_to_label.get(h["source_id"], ""))
        key = _chip_key(chip)
        if key in seen:
            continue
        seen.add(key)
        chips.append(chip)
    return chips
