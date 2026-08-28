"""Shared after-the-fact evidence search for the tools, with the same threshold as the chat."""

from src.features.ai_assistant.routes._chips import _line_segment_start
from src.features.ai_assistant.routes._evidence import (
    _ATTRIB_CANDIDATES,
    _GENERIC_ATTRIB_MAX_DIST,
    _MAX_CHIPS_PER_LINE,
    _is_seen,
    _pick_attribution,
)
from src.features.ai_assistant.routes._media_files import _load_transcript_segments

# Its own value, because a flashcard has no context the chat could measure against.
_TOOL_MULTI_CHIP_MAX_DELTA = 0.08

# Minimum length for an evidence anchor, short header lines would be a magnet.
_MIN_ATTRIB_CONTENT = 100


def _chip_key(chip: dict) -> tuple:
    """Identity of a nav chip: source + page (PDF) or timestamp (media)."""
    return (chip["source_label"], chip["page_number"], chip["start_time"])


def _chip_from_chunk(chunk: dict, label: str, claim: str = "",
                     segments: list[dict] | None = None) -> dict:
    """A chip to jump with: a timestamp for media, a page number for PDF."""
    st = chunk.get("start_time")
    if st is not None:
        if claim and segments:
            seg_start = _line_segment_start(claim, chunk, segments)
            if seg_start is not None:
                st = seg_start
        return {"source_label": label, "page_number": None, "start_time": st}
    return {"source_label": label, "page_number": chunk.get("page_number"), "start_time": None}


def _default_segments_fn():
    """Whisper segments per source, loaded once and then cached."""
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
    """Backs a batch of statements at once, one chip list per statement."""
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
                                           limit=_ATTRIB_CANDIDATES, fuzzy=False,
                                           # The restriction to seen pages belongs in the query, not in the filter.
                                           seen_pages=seen_pages_by_source)

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
    """Turns a statement's hits into source chips, or an empty list."""
    # Header fragments out, otherwise they become a magnet.
    hits = [h for h in hits if len(h.get("content") or "") >= _MIN_ATTRIB_CONTENT]
    if seen_pages_by_source is not None:
        hits = [h for h in hits if _is_seen(h, seen_pages_by_source)]
    best = _pick_attribution(hits, max_distance)
    if best is None:
        return []
    def _segs(hit: dict) -> list[dict] | None:
        """Fetch segments only for media hits, a PDF page needs none."""
        if segments_fn is None or hit.get("start_time") is None:
            return None
        return segments_fn(hit["source_id"])

    best_label = source_id_to_label.get(best["source_id"], "")
    chips = [_chip_from_chunk(best, best_label, claim, _segs(best))]
    if not multi:
        return chips

    seen = {_chip_key(chips[0])}
    best_dist = best["vec_distance"]
    # A pure keyword hit has no distance and must not be sorted along.
    for h in sorted(hits, key=lambda x: (x.get("vec_distance") is None,
                                         x.get("vec_distance") or 0.0)):
        if len(chips) >= _MAX_CHIPS_PER_LINE:
            break
        d = h.get("vec_distance")
        if d is None or d > max_distance or d - best_dist > _TOOL_MULTI_CHIP_MAX_DELTA:
            continue
        chip = _chip_from_chunk(h, source_id_to_label.get(h["source_id"], ""), claim, _segs(h))
        key = _chip_key(chip)
        if key in seen:
            continue
        seen.add(key)
        chips.append(chip)
    return chips
