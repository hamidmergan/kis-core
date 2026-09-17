"""Fetches the spots for an answer and packs them into one context window."""

import asyncio
import re
from bisect import bisect_left
from typing import Optional

from loguru import logger

from src import database as db
from src.limits import AIA_EMBED_QUERY_MAX_CHARS

from ._media_files import _enrich_media_content
from ._text import _format_timestamp


# Overview: a broad search sets the starting points, the top-up brings the breadth.
_GENERIC_RETRIEVE_LIMIT = 32


# Last resort: an even sample per source when the search finds nothing.
_GENERIC_FALLBACK_SAMPLE = 8


# How many hits serve as anchor points for the neighbour expansion.
_NEIGHBOR_ANCHORS = 24


# How many spots the global search returns before neighbours are added.
_GLOBAL_CANDIDATES = 120


# Intents that aim at breadth and may therefore see all the material.
_UEBERBLICK_INTENTS = ("GENERIC", "GREETING")


_NEIGHBOR_RADIUS = 3


# When two anchors are nearer than this, the gap between them is filled.
_NEIGHBOR_BRIDGE = 4


# Cap on concurrent queries, below the pool size.
_RETRIEVE_CONCURRENCY = 10


_retrieve_sem: Optional[asyncio.Semaphore] = None


# When the question names a source, that one is preferred.
_NAME_TITLE_CHARS = 400          # how much of page 1 counts as the self-naming "title"


_NAME_MIN_TOKEN_LEN = 5          # shorter tokens (der/die/und, abbreviations) are too loose


_NAME_BOOST_FACTOR = 0.95        # boosted distance = global_best * this → Primary, peers survive


_NAME_TOKEN_RE = re.compile(r"[^\W\d_]{%d,}" % _NAME_MIN_TOKEN_LEN, re.UNICODE)


def _get_retrieve_sem() -> asyncio.Semaphore:
    """Lazily create the shared retrieval semaphore (binds to the running loop)."""
    global _retrieve_sem
    if _retrieve_sem is None:
        _retrieve_sem = asyncio.Semaphore(_RETRIEVE_CONCURRENCY)
    return _retrieve_sem


def _truncate_query_for_embedding(text: str) -> str:
    """Shortens the search query before embedding, the full question still goes to the model."""
    if not text:
        return text
    return text[:AIA_EMBED_QUERY_MAX_CHARS]


def _title_word_match(token: str, hword: str) -> bool:
    """True when part of the question names a word from a source title."""
    if token == hword:
        return True
    # The typed stem must be long enough, otherwise it matches every statute.
    if len(token) >= 7 and hword.startswith(token) and len(hword) - len(token) >= 4:
        return True
    # question-side inflection of a substantial base name ("grundgesetzes"→"grundgesetz").
    if len(hword) >= 7 and token.startswith(hword) and len(token) - len(hword) <= 3:
        return True
    return False


def _named_source_ids(question: str, headers: dict[int, str]) -> set[int]:
    """Sources the question names, via an unambiguous title match."""
    qtokens = {m.group(0).lower() for m in _NAME_TOKEN_RE.finditer(question or "")}
    if not qtokens or not headers:
        return set()
    hdr_words = {sid: set(_NAME_TOKEN_RE.findall(h or "")) for sid, h in headers.items()}
    named: set[int] = set()
    for tok in qtokens:
        hits = [sid for sid, words in hdr_words.items()
                if any(_title_word_match(tok, w) for w in words)]
        if len(hits) == 1:
            named.add(hits[0])
    return named


def _reserve_question_budget(budget: int, question: str) -> int:
    """Subtracts the characters of the question from the context budget."""
    return max(1000, budget - len(question or "") - 200)


def _context_budget() -> int:
    """Character budget for the context, configurable in the admin area."""
    from src.features.ai_assistant.tasks._context_budget import context_budget
    return context_budget()


def _full_context_if_fits(source_ids: Optional[list[int]], max_chars: int) -> Optional[list[dict]]:
    """All chunks of the active sources, if together they fit the budget."""
    if not source_ids:
        return None  # keine Auswahl -> nichts zu laden, der Suchweg uebernimmt
    all_chunks: list[dict] = []
    total = 0
    for sid in source_ids:
        for c in db.get_aia_chunks_by_source(sid):
            total += len(c.get("content") or "")
            if total > max_chars:
                return None
            all_chunks.append(c)
    return all_chunks or None


async def _retrieve_generic_context(
    provider, workspace_id: int, source_ids: list[int], question: str,
    budget: int = 0,
) -> list[dict]:
    """Builds the overview context from one broad search plus coverage per source."""
    import asyncio
    # Caps the search query, the full question still goes to the model.
    question = _truncate_query_for_embedding(question)
    question_vector = await asyncio.to_thread(provider.embed_one, question)
    hits = await asyncio.to_thread(
        db.hybrid_search_chunks,
        workspace_id, question, question_vector, source_ids=source_ids,
        limit=_GENERIC_RETRIEVE_LIMIT, fuzzy=False,  # no trigram fuzzy: ~3s no-index scan, vector is already typo-robust
    )
    merged: list[dict] = []
    seen: set = set()
    for h in hits:
        key = (h["source_id"], h["page_number"], (h.get("content") or "")[:80])
        if key not in seen:
            seen.add(key)
            merged.append(h)

    if not source_ids or len(source_ids) <= 1:
        chunks = merged
    else:
        diverse, remaining, missing = _diversify_by_source(merged, source_ids)
        for sid in missing:
            per_source = await asyncio.to_thread(
                db.hybrid_search_chunks,
                workspace_id, question, question_vector, source_ids=[sid], limit=3,
            )
            if per_source:
                diverse.extend(per_source)
                continue
            raw = await asyncio.to_thread(db.get_aia_chunks_by_source, sid)
            if raw:
                diverse.append(raw[0])
        chunks = diverse + remaining

    # Last resort: an even sample of raw chunks.
    if not chunks:
        for sid in source_ids or []:
            _raw = await asyncio.to_thread(db.get_aia_chunks_by_source, sid)
            chunks.extend(_sample(_raw, _GENERIC_FALLBACK_SAMPLE))
    # Top up round robin across all sources, hits first.
    if budget and (source_ids or []):
        _OVERHEAD = 150  # ~chars for the <document>/<source>/<content> wrapper
        seen_keys = {(c["source_id"], c.get("page_number"), (c.get("content") or "")[:80]) for c in chunks}
        approx = sum(len(c.get("content") or "") + _OVERHEAD for c in chunks)
        pools: list[list[dict]] = []
        for sid in source_ids:
            _raw = await asyncio.to_thread(db.get_aia_chunks_by_source, sid)
            rem = [c for c in _raw
                   if (c["source_id"], c.get("page_number"), (c.get("content") or "")[:80]) not in seen_keys]
            pools.append(rem)
        progressing = True
        while approx < budget and progressing:
            progressing = False
            for pool in pools:
                if not pool:
                    continue
                cand = pool.pop(0)
                cost = len(cand.get("content") or "") + _OVERHEAD
                if approx + cost > budget:
                    pool.clear()  # this source's next chunk overflows -> stop pulling from it
                    continue
                chunks.append(cand)
                approx += cost
                progressing = True

    # _seq is the round per source so each keeps its best spots.
    seq_by_source: dict[int, int] = {}
    for c in chunks:
        sid = c["source_id"]
        c["_seq"] = seq_by_source.get(sid, 0)
        seq_by_source[sid] = c["_seq"] + 1

    from collections import Counter
    per_source = Counter(c["source_id"] for c in chunks)
    logger.info("Generic retrieval: {} chunks across {} sources (single wide search) | per-source: {}",
                len(chunks), len(source_ids or []), dict(per_source))
    return chunks


def _sample(items: list, k: int) -> list:
    """Evenly-spaced down-sample to at most ``k`` items, preserving order."""
    if len(items) <= k:
        return items
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


def _diversify_by_source(chunks: list[dict], source_ids: list[int]):
    """Reorders the hits so every source gets a representative first."""
    seen_sources: set[int] = set()
    diverse_chunks: list[dict] = []
    remaining: list[dict] = []
    for chunk in chunks:
        if chunk["source_id"] not in seen_sources:
            seen_sources.add(chunk["source_id"])
            diverse_chunks.append(chunk)
        else:
            remaining.append(chunk)
    missing = [sid for sid in source_ids if sid not in seen_sources]
    return diverse_chunks, remaining, missing


def _order_round_robin(chunks: list[dict], source_id_to_qnum: dict[int, int]) -> list[dict]:
    """Interleaves the chunks so every source keeps its early spots."""
    return sorted(
        chunks,
        key=lambda c: (c.get("_seq", 0), source_id_to_qnum.get(c["source_id"], 0)),
    )


def _take_chunks_within(hits: list[dict], char_share: int) -> list[dict]:
    """Takes the best chunks of a source until its share is full, at least one."""
    taken: list[dict] = []
    used = 0
    for i, c in enumerate(hits):
        clen = len(c.get("content") or "")
        if taken and used + clen > char_share:
            break
        c["_seq"] = i
        taken.append(c)
        used += clen
    return taken


def _expand_with_neighbors(
    anchors: list[dict],
    doc_chunks: list[dict],
    radius: int,
    source_id: int,
    bridge: int = _NEIGHBOR_BRIDGE,
) -> list[dict]:
    """Expands anchors into windows and closes gaps, the distance applies per spot."""
    pos = {c["id"]: i for i, c in enumerate(doc_chunks)}
    n = len(doc_chunks)
    # Anchors as a pair of spot and distance, sorted by spot.
    marks: list[tuple[int, float]] = []
    for a in anchors:
        i = pos.get(a["id"])
        if i is None:
            continue
        _fused = a.get("hybrid_score")
        if _fused is not None:
            key = -float(_fused)          # higher fused score -> smaller key
        else:
            _vd = a.get("vec_distance")
            key = float(_vd) if _vd is not None else 1.0
        marks.append((i, key))
    if not marks:
        return []
    marks.sort()
    mark_idx = [i for i, _d in marks]

    windows = sorted((max(0, i - radius), min(n - 1, i + radius)) for i, _d in marks)
    spans: list[list[int]] = [list(windows[0])]
    for lo, hi in windows[1:]:
        if lo - spans[-1][1] - 1 <= bridge:  # gap small enough -> merge + fill
            spans[-1][1] = max(spans[-1][1], hi)
        else:
            spans.append([lo, hi])

    def _nearest(j: int) -> tuple[float, int]:
        """Sort key and distance of the nearest anchor, via bisect instead of all comparisons."""
        k = bisect_left(mark_idx, j)
        best: Optional[tuple[int, float]] = None
        for cand in (k - 1, k):
            if 0 <= cand < len(marks):
                gap = abs(marks[cand][0] - j)
                key = (gap, marks[cand][1])
                if best is None or key < best:
                    best = key
        return (best[1], best[0]) if best else (1.0, 0)

    out: list[dict] = []
    for lo, hi in spans:
        for j in range(lo, hi + 1):
            c = dict(doc_chunks[j])
            c["source_id"] = source_id
            # Without the anchor distance the earlier spot wins instead of the carrying one.
            c["_anchor_dist"], c["_anchor_gap"] = _nearest(j)
            out.append(c)
    return out


async def _retrieve_specific_context(
    provider,
    workspace_id: int,
    search_source_ids: list[int],
    retrieval_queries: list[str],
    question: str,
    char_budget: int,
) -> list[dict]:
    """The retrieval path for specific questions: anchors per source plus neighbourhood."""
    # Cap each retrieval query (embed + lexical search) — see _truncate_query_for_embedding.
    _retrieval_queries = [_truncate_query_for_embedding(q) for q in retrieval_queries]
    _qvecs = await asyncio.to_thread(provider.embed, _retrieval_queries)
    _query_pairs = list(zip(_retrieval_queries, _qvecs))

    # Neighbour expansion: the answer almost always sits next to something findable.
    _sem = _get_retrieve_sem()

    # One search across all sources, then the best spots first.
    _kandidaten: dict[int, dict] = {}
    for _qtext, _qvec in _query_pairs:
        for a in (await asyncio.to_thread(
                db.hybrid_search_chunks, workspace_id, _qtext, _qvec,
                search_source_ids, _GLOBAL_CANDIDATES, fuzzy=False) or []):
            prev = _kandidaten.get(a["id"])
            if prev is None or (a.get("hybrid_score") or 0.0) > (prev.get("hybrid_score") or 0.0):
                _kandidaten[a["id"]] = a
    if not _kandidaten:
        logger.info("SPECIFIC: keine Treffer ueber {} Quellen", len(search_source_ids))
        return []

    # Each source fetches neighbours for itself, a window only holds inside a document.
    _je_quelle: dict[int, list[dict]] = {}
    for a in _kandidaten.values():
        _je_quelle.setdefault(a["source_id"], []).append(a)

    async def _fenster(sid: int, anker: list[dict]) -> tuple[list[dict], str]:
        async with _sem:
            doc = await asyncio.to_thread(db.get_chunks_by_source, sid)
        kopf = ((doc[0].get("content") if doc else None) or "")[:_NAME_TITLE_CHARS].lower()
        return _expand_with_neighbors(anker, doc, _NEIGHBOR_RADIUS, sid), kopf

    _fenster_ergebnis = await asyncio.gather(
        *[_fenster(sid, anker) for sid, anker in _je_quelle.items()])
    alle: list[dict] = [c for fenster, _kopf in _fenster_ergebnis for c in fenster]
    _headers = {sid: kopf for (sid, _a), (_f, kopf)
                in zip(_je_quelle.items(), _fenster_ergebnis)}

    # When the question names a source by title, its score is improved.
    if len(_je_quelle) > 1:
        _named = _named_source_ids(question, _headers)
        if _named:
            for c in alle:
                if c["source_id"] in _named:
                    c["_anchor_dist"] = c["_anchor_dist"] * _NAME_BOOST_FACTOR \
                        if c["_anchor_dist"] > 0 else c["_anchor_dist"] / _NAME_BOOST_FACTOR
            logger.info("SPECIFIC named-source boost → Quellen {}", sorted(_named))

    # Best spots first, then top up until the budget is full.
    alle.sort(key=lambda c: (c.get("_anchor_dist", 1.0), c.get("_anchor_gap", 0)))
    from src.features.ai_assistant.tasks._context_budget import specific_context_budget
    chunks = _take_chunks_within(alle, min(char_budget, specific_context_budget()))
    chunks.sort(key=lambda c: (
        c["source_id"],
        c.get("page_number") if c.get("page_number") is not None else -1,
        c.get("start_time") if c.get("start_time") is not None else -1.0,
        c.get("id") or 0,
    ))
    _used = sum(len(c.get("content") or "") for c in chunks)
    from collections import Counter as _Counter
    _per_src = _Counter(c["source_id"] for c in chunks)
    logger.info(
        "SPECIFIC global: {} chunks ({} chars) aus {} Quellen | je Quelle: {} "
        "| Kandidaten<={} Radius+-{} | Frage: '{}'",
        len(chunks), _used, len(_per_src), dict(_per_src), _GLOBAL_CANDIDATES,
        _NEIGHBOR_RADIUS, (_retrieval_queries[0] if _retrieval_queries else "")[:80],
    )
    return chunks


def _pack_context_batches(
    chunks: list[dict],
    budget: int,
    source_id_to_qnum: dict[int, int],
    all_sources_list: dict[int, dict],
    transcript_by_source: dict[int, list[dict]],
) -> tuple[list[str], dict[int, set]]:
    """Packs the chunks into one context block and reports the pages seen."""
    batches: list[str] = []
    cur_parts: list[str] = []
    cur_len = 0
    cid = 0
    seen_pages: dict[int, set] = {}
    media_sources: set[int] = set()

    def _build_part(chunk: dict, qn: int, _cid: int) -> str:
        src = all_sources_list.get(chunk["source_id"])
        fname = src["filename"] if src else f"source-{qn}"
        if chunk.get("start_time") is not None:
            segments = transcript_by_source.get(chunk["source_id"], [])
            content = _enrich_media_content(chunk, segments) if segments else chunk["content"]
            loc = _format_timestamp(chunk["start_time"])
        else:
            content = chunk["content"]
            # A summary of the whole source has no page of its own.
            loc = "summary" if chunk.get("page_number") is None else f"S. {chunk['page_number']}"
        return (f'<document index="{qn}" id="{_cid}">\n<source>{fname} | {loc}</source>\n'
                f'<content>\n{content}\n</content>\n</document>')

    def _flush() -> None:
        nonlocal cur_parts, cur_len, cid
        if cur_parts:
            batches.append(f"<documents>\n{''.join(cur_parts)}\n</documents>")
        cur_parts, cur_len, cid = [], 0, 0

    for chunk in chunks:
        qn = source_id_to_qnum.get(chunk["source_id"], 1)
        part = _build_part(chunk, qn, cid + 1)
        if cur_parts and cur_len + len(part) > budget:
            continue  # skip oversized, keep packing later smaller chunks
        cid += 1
        cur_parts.append(part)
        cur_len += len(part)
        if chunk.get("start_time") is not None:
            media_sources.add(chunk["source_id"])
        elif chunk.get("page_number") is not None:
            seen_pages.setdefault(chunk["source_id"], set()).add(chunk["page_number"])
    _flush()

    seen_pages_by_source: dict[int, set] = {sid: set() for sid in media_sources}
    for sid, pages in seen_pages.items():
        if sid not in media_sources:
            seen_pages_by_source[sid] = pages
    return batches, seen_pages_by_source
