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
    _ATTRIB_CANDIDATES,
    _is_seen,
    _line_segment_start,
    _load_transcript_segments,
    _GENERIC_ATTRIB_MAX_DIST,
    _MULTI_CHIP_MAX_DELTA,
    _MAX_CHIPS_PER_LINE,
)

# Minimum chunk length (chars) to be a citation anchor. Slide decks get chunked into tiny
# running-header/title fragments (e.g. "WISSENSCHAFTLICHES ARBEITEN UND PUBLIZIEREN? VON DER
# IDEE ZUR VERÖFFENTLICHUNG", ~80 chars). Such a generic title sits close to almost ANY query
# and becomes a "magnet" that mis-anchors short claims (a mindmap label) to its page. Real
# content chunks are 200+ chars and media transcript segments ~580 avg, so this floor drops the
# boilerplate without touching genuine matches.
_MIN_ATTRIB_CONTENT = 100


def _chip_key(chip: dict) -> tuple:
    """Identity of a nav chip: source + page (PDF) or timestamp (media)."""
    return (chip["source_label"], chip["page_number"], chip["start_time"])


def _chip_from_chunk(chunk: dict, label: str, claim: str = "",
                     segments: list[dict] | None = None) -> dict:
    """Nav-only structured chip. Media (has start_time) cites its timestamp and carries
    no page; a PDF cites its page. Mirrors the chat's ``_attribution_chip`` start-time-first
    rule so audio/video never gets a bogus "S. <segment-index>".

    Mit ``claim`` und den Whisper-``segments`` zeigt die Zeitmarke auf das Segment mit der
    zitierten Aussage statt auf den Anfang des ganzen Chunks (siehe
    :func:`_line_segment_start`). Ohne sie bleibt es beim Chunk-Anfang."""
    st = chunk.get("start_time")
    if st is not None:
        if claim and segments:
            seg_start = _line_segment_start(claim, chunk, segments)
            if seg_start is not None:
                st = seg_start
        return {"source_label": label, "page_number": None, "start_time": st}
    return {"source_label": label, "page_number": chunk.get("page_number"), "start_time": None}


def _default_segments_fn():
    """Whisper-Segmente je Quelle, einmal geladen und dann aus dem Gedaechtnis.

    Ein Werkzeug attribuiert dutzende Aussagen am Stueck, die fast alle auf dieselben
    paar Quellen zeigen. Ohne das Gedaechtnis waere das ein Griff in den Speicher pro
    Aussage. Gefragt wird nur fuer Medien-Treffer, eine reine PDF-Sammlung fasst die
    Ablage also gar nicht an."""
    cache: dict[int, list[dict]] = {}

    def load(source_id: int) -> list[dict]:
        if source_id not in cache:
            from src import database as db
            src = db.get_aia_source_by_id(source_id)
            cache[source_id] = _load_transcript_segments(src) if src else []
        return cache[source_id]

    return load


def attribute_claims(
    claims: list[str],
    source_id_to_label: dict[int, str],
    *,
    multi: bool = False,
    max_distance: float = _GENERIC_ATTRIB_MAX_DIST,
    workspace_id: int | None = None,
    source_ids: list[int] | None = None,
    seen_pages_by_source: dict | None = None,
    embed_fn=None,
    search_fn=None,
    segments_fn=None,
) -> list[list[dict]]:
    """Attribute a batch of claim texts to nav-only source chips, one chip-list per claim.

    Embeds ALL claims in ONE call (``embed_fn``), then per claim runs hybrid search
    (``search_fn``) scoped to ``source_ids`` and selects chips via :func:`chips_for_claim`.
    ``max_distance`` is the gate handed to the selector — a caller with thin claims (e.g. a
    mindmap's one-word node labels) can tighten it so weak matches abstain instead of citing a
    near-but-wrong page. ``seen_pages_by_source`` (optional) clamps chips to pages actually shown
    to the LLM, like the chat's seen-check. ``embed_fn``/``search_fn``/``segments_fn`` are
    injectable for testing; in production they default to the shared embedding provider,
    ``db.hybrid_search_chunks`` und den Whisper-Segmenten der Quelle."""
    if not claims:
        return []

    if segments_fn is None:
        segments_fn = _default_segments_fn()
    if embed_fn is None:
        from src.services.aia_embeddings import get_embedding_provider
        embed_fn = get_embedding_provider().embed
    if search_fn is None:
        from src import database as db

        def search_fn(text, vec):
            return db.hybrid_search_chunks(workspace_id, text, vec,
                                           source_ids=source_ids,
                                           limit=_ATTRIB_CANDIDATES, fuzzy=False)

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
                                   max_distance=max_distance,
                                   seen_pages_by_source=seen_pages_by_source,
                                   claim=claim, segments_fn=segments_fn))
    return out


def chips_for_claim(
    hits: list[dict],
    source_id_to_label: dict[int, str],
    *,
    multi: bool = False,
    max_distance: float = _GENERIC_ATTRIB_MAX_DIST,
    seen_pages_by_source: dict | None = None,
    claim: str = "",
    segments_fn=None,
) -> list[dict]:
    """Turn ranked search hits for one claim into nav-only structured source chips.

    With ``multi=True`` a claim genuinely drawn from several passages also cites the
    co-sources that sit CLOSE to the best one (within ``_MULTI_CHIP_MAX_DELTA``), deduped
    by source/page and capped at ``_MAX_CHIPS_PER_LINE`` — the same relative gate the chat
    uses, so a clearly-best single source never collects on-topic near-misses.

    ``seen_pages_by_source`` (optional) restricts hits to source/pages the LLM was actually
    shown (chat-style seen-check) BEFORE selecting — so a chip can never point at a page that
    was not in the generation context.

    ``claim`` ist der Text der Aussage und ``segments_fn`` liefert die Whisper-Segmente einer
    Quelle. Zusammen ruecken sie die Zeitmarke eines Medien-Chips auf das Segment mit der
    Aussage, statt auf den Anfang des ganzen Chunks zu zeigen.

    Returns ``[]`` when nothing lands within the distance gate (no fabricated source)."""
    # Drop boilerplate/title fragments so a generic running-header chunk can't become a magnet
    # that mis-anchors a thin claim (see _MIN_ATTRIB_CONTENT).
    hits = [h for h in hits if len(h.get("content") or "") >= _MIN_ATTRIB_CONTENT]
    if seen_pages_by_source is not None:
        hits = [h for h in hits if _is_seen(h, seen_pages_by_source)]
    best = _pick_attribution(hits, max_distance)
    if best is None:
        return []
    def _segs(hit: dict) -> list[dict] | None:
        """Segmente nur fuer Medien-Treffer holen, eine PDF-Seite braucht keine."""
        if segments_fn is None or hit.get("start_time") is None:
            return None
        return segments_fn(hit["source_id"])

    best_label = source_id_to_label.get(best["source_id"], "")
    chips = [_chip_from_chunk(best, best_label, claim, _segs(best))]
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
        chip = _chip_from_chunk(h, source_id_to_label.get(h["source_id"], ""), claim, _segs(h))
        key = _chip_key(chip)
        if key in seen:
            continue
        seen.add(key)
        chips.append(chip)
    return chips
