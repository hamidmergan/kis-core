"""AI assistant routes - chat + RAG."""

import asyncio
import io
import json
import re
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale, t
from src.limits import (
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
    AIA_WORKSPACE_MAX_ACCESS_LINKS,
    AIA_NOTES_MAX_PER_USER,
    AIA_CONTEXT_MAX_CHARS,
    AIA_CONTEXT_HARD_CAP,
)
from src.security.rate_limit import enforce_burst
from src.security.usage_log import log_request as _log_usage
from src.storage import USE_S3, delete_file, file_exists, get_file
from src.tool_prompts import (
    AIA_SYSTEM_DIRECT,
    AIA_SYSTEM_DIRECT_WITH_CONTEXT,
    aia_system_rag,
    aia_rag_user_message,
    aia_reduce_user_message,
    AIA_POPUP_ACTIONS,
    AIA_INTENT_CLASSIFIER_SYSTEM,
    AIA_INTENT_CLASSIFIER_FEWSHOT,
    AIA_SCOPE_EXTRACTOR_SYSTEM,
    AIA_QUERY_UNDERSTANDING_SYSTEM,
)

# Upper bound on the question length we hand to the LLM intent classifier.
# Longer questions are nearly always topic-specific (no need for an LLM round-trip)
# and very long inputs blow up the cheap-pre-filter premise of the classifier call.
_INTENT_MAX_WORDS = 30

# GENERIC (overview) retrieval: ONE wide hybrid search seeds the most on-topic
# chunks; the round-robin budget top-up below (document order) then fills the rest
# so the overview spans the whole content. No sub-query decomposition / strategy
# LLM call — for a broad question semantic relevance is weak, so COVERAGE (the
# fill) does the real work. The wide limit keeps breadth at/above the old 4-query
# fan-out (4x8). The shared char budget at the call site truncates the result.
_GENERIC_RETRIEVE_LIMIT = 32
# Absolute fallback only: even-spread raw-chunk sample per source when retrieval
# returns nothing matchable (e.g. media with no searchable text).
_GENERIC_FALLBACK_SAMPLE = 8

# Page-scoped retrieval: when a question names an explicit page ("fasse Seite 5
# zusammen", "summarize page 12") we skip semantic search and hand the model
# exactly that page's chunks. The number alone is a poor search token (it rarely
# appears in the page's text), so hybrid search would miss the actual page.
#
# Anchor on a page keyword so a bare number ("die 5 wichtigsten Punkte") never
# triggers scoping. The keyword set is deliberately small and abbreviation-heavy
# (de "Seite"/"S.", en "page"/"p./pp.") — the universal forms cover the KIS
# languages; an unknown form simply falls through to normal retrieval. Ranges
# ("Seite 5-7", "Seiten 5 bis 7") expand; an absurd span collapses to the start
# so "page 1-9999" can't drag in the whole document.
_PAGE_REF_RE = re.compile(
    r"\b(?:S\.\s*|Seiten?\s*|pp?\.\s*|pages?\s*)"
    r"(\d{1,4})"
    # Range connector: any mix of hyphens and/or the word bis/to (typos and glued
    # tokens like "12-14", "12 -bis 14", "12 bis-14", "12 — 14"). At least one such
    # token is required, so a bare space ("12 14") is NOT read as a range.
    r"(?:\s*(?:[-–—]+\s*(?:bis|to)?|bis|to)\s*[-–—]*\s*(\d{1,4}))?",
    re.IGNORECASE,
)
_MAX_PAGE_SPAN = 50

# Source-distance gate: drop a source whose CLOSEST chunk is farther than this multiple
# of the best source's closest chunk (off-topic). Cosine distance is stopword-immune →
# language-agnostic, no word lists.
_DIST_FACTOR = 999  # gate effektiv AUS: 1.3 verwarf bei Mehr-Quellen-/Zählfragen echte Quellen
# Floor of the per-source CHAR allotment in the SPECIFIC budget split: every on-topic
# source (one that passed the gate) is guaranteed at least this many chars of its top
# chunks, so a question whose answer is spread across many docs (e.g. each doc names
# one author) keeps every doc represented. ~4-5 chunks.
_SPECIFIC_FLOOR_CHARS = 4000
# Neighbor-chunk expansion (SPECIFIC, single call): how many top hybrid hits per
# source act as expansion ANCHORS, and how many document neighbours to pull around
# each (±radius). A fact often sits NEXT TO a hit (author name beside the "Autoren"
# heading), so the window catches it without reading the whole document. ~24x(2*3+1)
# ≈ 168 chunks worst case before dedup — comfortably one context window.
_NEIGHBOR_ANCHORS = 24
_NEIGHBOR_RADIUS = 3
# Bridge anchors whose ±radius windows are within this many chunks of each other:
# fill the gap so two anchors that BRACKET the answer pull the chunks between them
# (a co-author named between the "Autoren" heading and the contact section).
_NEIGHBOR_BRIDGE = 4


def _parse_page_refs(question: str) -> list[int]:
    """Extract explicit page numbers from a question. Returns them sorted and
    de-duplicated (ranges expanded); empty when no page is named, so the caller
    falls back to normal retrieval. See _PAGE_REF_RE for the recognised forms."""
    pages: set[int] = set()
    for m in _PAGE_REF_RE.finditer(question or ""):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if end < start:
            start, end = end, start
        if end - start > _MAX_PAGE_SPAN:
            end = start
        pages.update(range(start, end + 1))
    return sorted(pages)


def _first_source_kind(source_ids: Optional[list[int]], sources_by_id: dict[int, dict]) -> Optional[str]:
    """Classify the FIRST selected source as ``"pdf"`` / ``"media"`` / None.

    Scope ("Seite 5", "Minute 10") applies to the lead source — with several
    sources it is ambiguous which one, so we take the first and ignore the rest.
    PDFs carry pages, media carries timestamps; anything else has neither → None."""
    if not source_ids:
        return None
    src = sources_by_id.get(source_ids[0])
    if not src:
        return None
    suffix = Path(src["filename"]).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in _MEDIA_EXTENSIONS:
        return "media"
    return None


def _parse_scope_response(content: str) -> dict:
    """Parse the scope extractor's reply into ``{"unit", "intervals"}``.

    Tolerant: strips <think> blocks and code fences, finds the first JSON object,
    coerces ``unit`` to page/time/unknown/None and keeps only well-formed
    ``[from, to]`` intervals (``to`` may be null for an open end). Any garbage →
    empty scope, so the caller falls back to the regex / normal retrieval."""
    raw = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    raw = raw.replace("```json", "").replace("```", "")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"unit": None, "intervals": []}
    try:
        data = json.loads(m.group(0))
    except Exception:
        return {"unit": None, "intervals": []}
    unit = data.get("unit")
    if unit not in ("page", "time", "unknown"):
        unit = None
    intervals: list[list] = []
    for it in data.get("intervals") or []:
        if not isinstance(it, (list, tuple)) or len(it) != 2:
            continue
        a, b = it
        if not isinstance(a, int) or isinstance(a, bool):
            continue
        if b is not None and (not isinstance(b, int) or isinstance(b, bool)):
            continue
        intervals.append([a, b])
    return {"unit": unit, "intervals": intervals}


async def _extract_query_scope(llm, question: str) -> dict:
    """Self-Query pre-call: extract an explicit page/time scope from the question.

    Runs in a worker thread (sync client) so it can sit in an ``asyncio.gather``
    next to the intent classifier — both pre-calls overlap, so wall-clock latency
    is ~that of one call. Any failure → empty scope (regex fallback covers pages)."""
    def _call():
        return llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system", "content": AIA_SCOPE_EXTRACTOR_SYSTEM},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=200,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
    try:
        response = await asyncio.to_thread(_call)
        msg = response.choices[0].message
        raw = msg.content or getattr(msg, "reasoning_content", None) or ""
    except Exception as e:
        logger.warning("Scope extractor failed, no scope: {}", e)
        return {"unit": None, "intervals": []}
    scope = _parse_scope_response(raw)
    logger.info("Scope extractor: '{}' → {}", question[:50], scope)
    return scope


_MAX_TIME_SPAN_SEC = 6 * 3600  # safety cap so an open/absurd time range can't pull everything


def _expand_page_intervals(intervals: list[list], max_page: Optional[int]) -> list[int]:
    """Expand ``[[from, to], ...]`` page intervals to a sorted page list. An open end
    (``to is None``) runs to ``max_page``; an absurd span collapses to the start
    (a typo'd "1-9999" must not drag in the whole document)."""
    pages: set[int] = set()
    for a, b in intervals:
        if b is None:
            b = max_page if max_page is not None else a
        lo, hi = (a, b) if a <= b else (b, a)
        if hi - lo > _MAX_PAGE_SPAN:
            hi = lo
        pages.update(range(lo, hi + 1))
    return sorted(p for p in pages if p >= 1)


def _page_scope_too_large(intervals: list[list], max_page: Optional[int], limit: int) -> bool:
    """True when the requested page scope spans more than ``limit`` pages — i.e. it
    covers (most of) the document. That is an overview request, not a precise scope:
    the small candidate set is what makes scoping accurate, and a huge range won't fit
    the context budget anyway. The caller routes such asks to GENERIC instead of
    scoping. Cheap span count (no list build); overlaps over-count, which is safe."""
    total = 0
    for a, b in intervals:
        if b is None:
            b = max_page if max_page is not None else a
        lo, hi = (a, b) if a <= b else (b, a)
        total += hi - lo + 1
        if total > limit:
            return True
    return False


def _time_intervals_to_seconds(intervals: list[list], max_seconds: Optional[float]) -> list[tuple]:
    """Convert MINUTE intervals to inclusive second windows. A point ``[10,10]`` →
    the whole 10th minute ``(600, 660)``; a range ``[10,12]`` → ``(600, 780)``; an
    open end → up to ``max_seconds``. Span-capped so an open/absurd range stays sane."""
    out: list[tuple] = []
    for a, b in intervals:
        if b is None:
            lo = max(0, a)
            lo_sec = lo * 60
            hi_sec = max_seconds if max_seconds is not None else (lo + 1) * 60
        else:
            lo, hi = (a, b) if a <= b else (b, a)
            lo_sec, hi_sec = max(0, lo) * 60, (hi + 1) * 60
        if hi_sec - lo_sec > _MAX_TIME_SPAN_SEC:
            hi_sec = lo_sec + 60
        out.append((lo_sec, hi_sec))
    return out


def _retrieve_page_scoped_context(source_ids: list[int], pages: list[int]) -> list[dict]:
    """Load the given sources' chunks and keep only those on the requested pages.
    Document order is preserved (get_aia_chunks_by_source orders by page/time)."""
    wanted = set(pages)
    chunks: list[dict] = []
    for sid in source_ids:
        chunks.extend(
            c for c in db.get_aia_chunks_by_source(sid) if c.get("page_number") in wanted
        )
    return chunks


def _retrieve_time_scoped_context(source_id: int, ranges_seconds: list[tuple]) -> list[dict]:
    """Load a media source's chunks and keep those whose ``[start_time, end_time]``
    overlaps any requested second window. Non-media chunks (no start_time) are skipped."""
    chunks: list[dict] = []
    for c in db.get_aia_chunks_by_source(source_id):
        st = c.get("start_time")
        if st is None:
            continue
        en = c.get("end_time")
        if en is None:
            en = st
        if any(st < r_end and en > r_start for r_start, r_end in ranges_seconds):
            chunks.append(c)
    return chunks


# Generic can't-help message for an explicit page/time request we cannot serve
# (page/minute absent, or the lead source is the wrong kind). DELIBERATELY distinct
# from the "no info in the sources" content sentinel: that one signals a real topic
# gap (valuable — the material genuinely lacks the answer) and must stay. This one
# says only "I can't do this particular scope request", so a structural ask never
# masquerades as a content verdict. Localised by the user's chat language (de default).
_SCOPE_UNFULFILLABLE_MSG = {
    "de": "Dabei kann ich dir leider nicht weiterhelfen. Bitte formuliere deine Frage anders oder wähle die passende Quelle aus.",
    "en": "I'm afraid I can't help with that. Please rephrase your question or select the relevant source.",
}


def _scope_unfulfillable_message(scope_requested: bool, scope_chunks, chat_lang: str) -> Optional[str]:
    """Return a generic can't-help message when a page/time scope was explicitly
    requested but could not be served (``scope_chunks`` empty/None), else None.
    Kept separate from the 'no info in sources' sentinel — see _SCOPE_UNFULFILLABLE_MSG."""
    if scope_requested and not scope_chunks:
        return _SCOPE_UNFULFILLABLE_MSG.get(chat_lang, _SCOPE_UNFULFILLABLE_MSG["de"])
    return None


async def _classify_intent(llm, question: str) -> str:
    """Decide GENERIC (cross-source overview) vs SPECIFIC (topic-focused) for routing.

    Single small LLM call - language-agnostic, replaces the old DE/EN regex list.
    On any error or unexpected output we fall back to SPECIFIC, the more
    conservative path (hybrid search still works for overview-ish questions,
    just costs more tokens). Runs in a worker thread so a stalled provider
    cannot block the FastAPI event loop.
    """
    import asyncio
    raw = ""
    def _call():
        # 60s covers Ollama cold-start model load on first request after
        # provider switch / restart. Warm calls return in ~500ms anyway.
        return llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system", "content": AIA_INTENT_CLASSIFIER_SYSTEM},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=200,  # leave headroom for reasoning preambles; we parse the verdict out
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
    try:
        response = await asyncio.to_thread(_call)
        msg = response.choices[0].message
        raw = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
        # Strip <think>...</think> blocks (reasoning models) before parsing
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    except Exception as e:
        logger.warning("Intent classifier failed, defaulting to SPECIFIC: {}", e)
        return "SPECIFIC"
    # Some models echo punctuation, quote marks, the prefix "Q:", or reply in the
    # source language. Normalise hard and check for the GENERIC token anywhere.
    cleaned = re.sub(r"[^A-Za-z]+", " ", raw).upper().strip()
    verdict = "GENERIC" if "GENERIC" in cleaned.split() else "SPECIFIC"
    logger.info("Intent classifier raw='{}' → {}", raw[:50], verdict)
    return verdict


def _parse_understanding(content: str) -> tuple[str, dict]:
    """Parse the combined query-understanding reply into ``(intent, scope)``.

    Tolerant: strips <think>/code-fences, takes the first JSON object. ``intent``
    defaults to SPECIFIC (the conservative route); ``scope`` is validated by
    ``_parse_scope_response``. If the JSON is broken we still salvage a GENERIC
    token if present. Any garbage → ``("SPECIFIC", {"unit": None, "intervals": []})``."""
    import json
    raw = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    raw = raw.replace("```json", "").replace("```", "")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return "SPECIFIC", {"unit": None, "intervals": []}
    try:
        obj = json.loads(m.group(0))
    except Exception:
        cleaned = re.sub(r"[^A-Za-z]+", " ", raw).upper().split()
        return ("GENERIC" if "GENERIC" in cleaned else "SPECIFIC"), {"unit": None, "intervals": []}
    intent = "GENERIC" if "GENERIC" in str(obj.get("intent", "")).upper() else "SPECIFIC"
    scope_obj = obj.get("scope")
    scope = _parse_scope_response(json.dumps(scope_obj)) if scope_obj else {"unit": None, "intervals": []}
    return intent, scope


async def _understand_query(llm, question: str) -> tuple[str, dict]:
    """ONE pre-call that does BOTH query-understanding jobs in a single round-trip:
    route GENERIC vs SPECIFIC AND extract any explicit page/time scope. Replaces the
    two separate pre-calls (intent classifier + scope extractor). Returns
    ``(intent, scope)``. On any failure → ``("SPECIFIC", empty scope)`` — the
    conservative route; the regex fallback still covers simple page refs downstream.
    Runs in a worker thread so a stalled provider cannot block the event loop."""
    import asyncio
    def _call():
        # 60s covers Ollama cold-start; warm calls return in ~500ms.
        return llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system", "content": AIA_QUERY_UNDERSTANDING_SYSTEM},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=200,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
    try:
        response = await asyncio.to_thread(_call)
        msg = response.choices[0].message
        raw = msg.content or getattr(msg, "reasoning_content", None) or ""
    except Exception as e:
        logger.warning("Query understanding failed, defaulting to SPECIFIC/no-scope: {}", e)
        return "SPECIFIC", {"unit": None, "intervals": []}
    intent, scope = _parse_understanding(raw)
    logger.info("Query understanding: '{}' → intent={} scope={}", question[:50], intent, scope)
    return intent, scope


def _context_budget() -> int:
    """Character budget for the LLM context, admin-tunable per deployment.

    KIS runs on very different setups — universities on large cloud models vs a
    private user on a local Ollama — so a fixed budget is wrong. Reads the
    ``aia_context_max_chars`` admin setting, falling back to AIA_CONTEXT_MAX_CHARS
    (250k chars ≈ 71k tokens, sized for the Mid minimum tier). A deployment can
    raise it toward AIA_CONTEXT_HARD_CAP so whole large documents fit (see
    _full_context_if_fits) and SPECIFIC needs fewer map-reduce calls; an admin
    value already in the DB overrides this default.
    """
    try:
        value = int(db.get_setting("aia_context_max_chars", str(AIA_CONTEXT_MAX_CHARS)))
    except (ValueError, TypeError):
        return AIA_CONTEXT_MAX_CHARS
    # Clamp on read too: a stale/oversized value in the DB (set before the cap,
    # or written directly) must never push a context the model can't take.
    return max(1000, min(value, AIA_CONTEXT_HARD_CAP))


def _full_context_if_fits(source_ids: list[int], max_chars: int) -> Optional[list[dict]]:
    """Return ALL chunks of the active sources iff their total fits the budget.

    For an overview/summary question over source(s) small enough to fit the
    context window, sending the full content beats retrieving a sample: the LLM
    sees the whole document, nothing is missed, and we skip the strategy LLM call
    entirely. Short-circuits to None as soon as the running total exceeds the
    budget, so a 117-page doc bails cheaply and falls back to retrieval.
    """
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
    """Build the GENERIC (overview) context purely from pgvector retrieval.

    Runs the question through ONE wide hybrid search, dedups the hits, then
    guarantees every active source is represented (per-source mini-search
    fallback, then the source's first chunk). The round-robin budget top-up below
    fills the rest of the context in document order, so the overview spans the
    whole content — no sub-query decomposition and no strategy LLM call (for a
    broad question relevance is weak; coverage does the real work). No summaries
    involved — chunks + embeddings are the only precomputed data.
    """
    import asyncio
    question_vector = await asyncio.to_thread(provider.embed_one, question)
    hits = db.hybrid_search_chunks(
        workspace_id, question, question_vector, source_ids=source_ids,
        limit=_GENERIC_RETRIEVE_LIMIT,
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
            per_source = db.hybrid_search_chunks(
                workspace_id, question, question_vector, source_ids=[sid], limit=3,
            )
            if per_source:
                diverse.extend(per_source)
                continue
            raw = db.get_aia_chunks_by_source(sid)
            if raw:
                diverse.append(raw[0])
        chunks = diverse + remaining

    # Absolute fallback: retrieval returned nothing (e.g. media with no matchable
    # text). Hand over an even-spread sample of raw chunks so the LLM still sees
    # the document; the char budget at the call site truncates the rest.
    if not chunks:
        for sid in source_ids or []:
            chunks.extend(_sample(db.get_aia_chunks_by_source(sid), _GENERIC_FALLBACK_SAMPLE))
    # Budget top-up: relevance retrieval (max ~32 chunks) typically leaves the
    # overview context budget half-empty, so the summary only sees a fraction of
    # the material and a source can end up with a single chunk. Fill the rest of
    # the budget ROUND-ROBIN across sources (document order) — relevance chunks
    # stay first, then each source contributes more in turn until the budget is
    # (approximately) full. The call-site assembly loop is the exact char guard.
    if budget and (source_ids or []):
        _OVERHEAD = 150  # ~chars for the <document>/<source>/<content> wrapper
        seen_keys = {(c["source_id"], c.get("page_number"), (c.get("content") or "")[:80]) for c in chunks}
        approx = sum(len(c.get("content") or "") + _OVERHEAD for c in chunks)
        pools: list[list[dict]] = []
        for sid in source_ids:
            rem = [c for c in db.get_aia_chunks_by_source(sid)
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

    # Tag each chunk with its per-source round index (_seq) so the downstream
    # _order_round_robin interleaves sources fairly: round 0 of every source
    # first, then round 1, ... When the char budget truncates it drops the late
    # rounds, so every source keeps its early (most representative) chunks instead
    # of one whole source being cut off the end. _seq 0 = the source's first
    # (most relevant) chunk, since relevance hits precede the doc-order fill.
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


def _should_skip_intent_classification(source_text, source_ids, question: str) -> bool:
    """Cheap pre-filter: skip the LLM intent call when the route is obvious.

    Popup actions carry ``source_text`` and are always topic-focused; no
    sources means hybrid search is the only option; very long questions are
    nearly always specific and blow up the classifier premise. All -> SPECIFIC.
    """
    return (
        bool(source_text)
        or not source_ids
        or len(question.strip().split()) > _INTENT_MAX_WORDS
    )


def _sample(items: list, k: int) -> list:
    """Evenly-spaced down-sample to at most ``k`` items, preserving order."""
    if len(items) <= k:
        return items
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


def _diversify_by_source(chunks: list[dict], source_ids: list[int]):
    """Reorder hybrid-search hits so each source gets a representative first.

    Returns ``(diverse, remaining, missing)``: one chunk per seen source up
    front, the rest deferred, and the ``source_ids`` that produced no hit at all
    (the caller backfills those via per-source search / raw chunks).
    """
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
    """Interleave chunks so each source's Nth segment precedes any (N+1)th.

    Sorts stably by ``(_seq, panel_order)``: generic segments carry a per-source
    sequence index (``_seq`` 0,1,2…) so round 0 of every source comes first, then
    round 1, and so on — when the downstream char budget truncates, it cuts the
    late rounds and every source keeps its early (most representative) segments.

    Chunks without ``_seq`` (the SPECIFIC path) all sort as round 0, so the
    secondary panel-order key simply groups them by source as before.
    """
    return sorted(
        chunks,
        key=lambda c: (c.get("_seq", 0), source_id_to_qnum.get(c["source_id"], 0)),
    )


def _take_chunks_within(hits: list[dict], char_share: int) -> list[dict]:
    """Take a source's TOP chunks (hits are RRF-ranked, most relevant first) until
    their content fills ``char_share``. Always takes at least one chunk so a source
    is never represented by nothing. Tags each with ``_seq`` = its per-source
    relevance rank, so _order_round_robin can interleave sources fairly."""
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


def _allocate_specific_budget(
    kept: list[tuple[list[dict], Optional[float]]],
    char_budget: int,
) -> list[dict]:
    """Relevance-weighted per-source chunk budget for SPECIFIC (Option 2).

    ``kept`` = the on-topic sources (those that passed the distance gate) as
    ``(hits, src_best_distance)`` pairs, hits RRF-ranked. Instead of dumping ALL
    of every source's ~160 hits (mostly noise — only a handful actually bear on a
    fact/name question), we split ONE total char budget across the sources:

    - **More on-topic → more chars.** Weight = how far inside the gate the source
      sits (``threshold - src_best``); a borderline source gets little, a strongly
      on-topic one gets the bulk. Falls back to equal weights without distances.
    - **Floor per source** (``_SPECIFIC_FLOOR_CHARS``, capped so floors never
      exceed the budget) so every on-topic doc is represented — the "each doc
      names one author" case keeps all docs. The remainder is distributed by
      weight on top of the floors, so total CONTENT ≈ char_budget (≈ one context
      window). With the per-chunk XML wrapper added at pack time the wrapped
      context is usually one batch, occasionally two when a small tail spills —
      answered as parallel map + reduce, far below the old "all hits" cost.
    - **Single source** gets the whole budget → a deep hit (rank ~58) still fits.

    Total stays ≤ char_budget, so nothing is silently dropped *below* the budget;
    what is dropped is each source's long low-relevance tail (the noise), which is
    the whole point.
    """
    if not kept:
        return []
    if len(kept) == 1:
        return _take_chunks_within(kept[0][0], char_budget)

    dists = [d for _, d in kept if d is not None]
    threshold = (min(dists) * _DIST_FACTOR) if dists else None
    weights: list[float] = []
    for _hits, d in kept:
        if threshold is not None and d is not None:
            weights.append(max(threshold - d, 0.0))
        else:
            weights.append(1.0)
    wsum = sum(weights)
    if wsum <= 0:
        weights = [1.0] * len(kept)
        wsum = float(len(kept))

    # Floor first (capped so floors fit the budget), distribute the rest by weight.
    floor = min(_SPECIFIC_FLOOR_CHARS, char_budget // len(kept))
    remaining = max(0, char_budget - floor * len(kept))
    out: list[dict] = []
    for (hits, _d), w in zip(kept, weights):
        share = floor + int(remaining * w / wsum)
        out.extend(_take_chunks_within(hits, share))
    return out


def _expand_with_neighbors(
    anchors: list[dict],
    doc_chunks: list[dict],
    radius: int,
    source_id: int,
    bridge: int = _NEIGHBOR_BRIDGE,
) -> list[dict]:
    """Expand relevance ANCHORS into ±``radius`` document windows, bridging gaps.

    ``anchors`` = the source's top hybrid hits (carry ``id`` + ``vec_distance``).
    ``doc_chunks`` = the SAME source's chunks in document order (id, page_number,
    content, start/end_time). Each anchor becomes a window ``[i-radius, i+radius]``;
    windows whose gap is ``<= bridge`` are merged so two anchors that BRACKET the
    answer also pull the chunks between them. Returns the covered chunks in document
    order, each tagged with ``_anchor_dist`` (the merged span's best/smallest anchor
    distance) so the caller can trim to one context window best-first.

    Why: a fact often sits NEXT TO a hit, or BETWEEN two hits, rather than in either
    (a co-author named between the "Autoren" heading and the contact section). The
    window + bridge catches it in a single coherent call — no whole-document read.
    """
    pos = {c["id"]: i for i, c in enumerate(doc_chunks)}
    n = len(doc_chunks)
    windows: list[tuple[int, int, float]] = []
    for a in anchors:
        i = pos.get(a["id"])
        if i is None:
            continue
        ad = a.get("vec_distance")
        ad = ad if ad is not None else 1.0
        windows.append((max(0, i - radius), min(n - 1, i + radius), ad))
    if not windows:
        return []
    windows.sort()
    spans: list[list] = [list(windows[0])]
    for lo, hi, ad in windows[1:]:
        if lo - spans[-1][1] - 1 <= bridge:  # gap small enough -> merge + fill
            spans[-1][1] = max(spans[-1][1], hi)
            spans[-1][2] = min(spans[-1][2], ad)
        else:
            spans.append([lo, hi, ad])
    out: list[dict] = []
    for lo, hi, ad in spans:
        for j in range(lo, hi + 1):
            c = dict(doc_chunks[j])
            c["source_id"] = source_id
            c["_anchor_dist"] = ad
            out.append(c)
    return out


def _pack_context_batches(
    chunks: list[dict],
    budget: int,
    source_id_to_qnum: dict[int, int],
    all_sources_list: dict[int, dict],
    transcript_by_source: dict[int, list[dict]],
    *,
    multi: bool,
) -> tuple[list[str], dict[int, set]]:
    """Pack chunks into ``<documents>`` context strings, each ≤ ``budget`` chars.

    ``multi=False`` (GENERIC / SCOPE / popup): produces a SINGLE batch; a chunk
    that would overflow the budget is skipped (an overview need not see
    everything, and later smaller chunks may still fit).

    ``multi=True`` (SPECIFIC): NEVER drops a retrieved hit. When the current
    batch is full it opens another one, so every per-source hybrid hit is shown
    to the model across calls. The caller answers each batch and merges the
    results (map-reduce), which is why a deep fact (e.g. an author on fused rank
    ~59) can no longer be silently truncated out of the context.

    Each batch is its own LLM context window, so chunk ids (``id="N"``) restart at
    1 within every batch. Returns ``(batches, seen_pages_by_source)`` where
    ``seen_pages_by_source`` is the UNION of the pages the model saw across ALL
    batches (media sources map to an EMPTY set → the attribution cross-check
    reads that as "source retrieved, accept", since a timestamp chip has no page
    to validate). An empty ``chunks`` yields ``([], {})``.
    """
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
            loc = f"S. {chunk['page_number']}"
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
            if not multi:
                continue  # single batch: skip oversized, keep packing later smaller chunks
            _flush()
            part = _build_part(chunk, qn, cid + 1)  # cid reset → id restarts at 1
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


from src.features.ai_assistant.routes._helpers import (
    _trace_llm,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_workspace,
    _save_source_file,
    _delete_source_files_for_workspace,
    _resolve_source_ids,
    _term_appears_in_text,
    _load_transcript_segments,
    _enrich_media_content,
    _RepetitionGuard,
    _dedup_repeated_lines,
    _strip_inline_citation_chips,
    _attribute_generic_text,
    _needs_attribution,
    _append_scope_anchor,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
    _sanitize_citations,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: chat"])


def _stream_usage_tokens(chunk) -> tuple[Optional[int], Optional[int]]:
    """Extract (tokens_in, tokens_out) from a streaming chunk.

    With ``stream_options={"include_usage": True}`` the final chunk of an
    OpenAI-compatible stream carries a ``usage`` object; normal content chunks
    do not. Providers that don't support it send ``usage=None``. Returns
    ``(None, None)`` whenever usage is absent so the caller can keep the last
    real value.
    """
    usage = getattr(chunk, "usage", None)
    if usage is None:
        return None, None
    return (
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


def _enrich_chat_trace(trace_id, question, answer, *, user_id, session_id) -> None:
    """Upsert the aia-chat trace with the real question/answer + user/session.

    ``@observe`` finalizes the trace when ``chat()`` returns its
    StreamingResponse, but the answer is only produced LATER inside the
    streaming generator — outside the observe context. So we write back by
    trace id via the client (captured while still in context) instead of
    ``update_current_observation``, which would target a closed context.
    Tracing must never break the user-facing response, so failures are
    swallowed.
    """
    if not trace_id:
        return
    try:
        langfuse_context.client_instance.trace(
            id=trace_id,
            input=question,
            output=answer,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        pass


@router.post("/ai-assistant/workspaces/{workspace_uuid}/chat")
@observe(name="aia-chat")
async def chat(
    workspace_uuid: str,
    body: schemas.ChatBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
    llm=Depends(get_llm_client),
    locale: str = Depends(get_locale),
):
    import time as _time
    _trace_llm(llm, "aia-chat")
    user_id = current_user["user_id"]
    logger.info("Chat: request received user={} workspace={}", user_id, workspace_uuid[:8])
    # Captured here while still inside the @observe context; the streaming
    # generator runs after this function returns, so it can no longer reach
    # the trace via context — only by id.
    try:
        _trace_id = langfuse_context.get_current_trace_id()
    except Exception:
        _trace_id = None

    # Burst block: at >50 chat requests in 60s the user is blocked for 10 min.
    # Raises 429 if currently blocked or the limit is being exceeded right now.
    enforce_burst(user_id, locale)

    _started_at = _time.monotonic()
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    # Per-(workspace, user) AI tutor language; drives the locale-specific
    # "no info" sentinel injected into the RAG system prompt.
    chat_lang = (db.get_aia_user_settings(workspace["id"], user_id) or {}).get("chat_lang", "de")

    # Resolve enrollment_id for per-link chat separation (needed for history fetch)
    enrollment_id = body.enrollment_id if not is_owner else None

    # Sync workspace status: heal stale 'pending' if all sources are actually ready
    if workspace["status"] != "ready":
        sources_check = db.get_aia_sources_by_workspace(workspace["id"])
        ready_sources = [s for s in sources_check if s["status"] == "ready"]
        if not ready_sources:
            raise HTTPException(status_code=409, detail=t("ai.chat.noIndexedSources", locale))
        if all(s["status"] == "ready" for s in sources_check):
            db.update_aia_workspace_status(workspace_uuid, "ready")

    # Resolve active_source_ids (UUIDs → DB int ids). Keep the resolved source
    # dicts so the page-scope gate can check single-source-and-PDF without a refetch.
    source_ids: list[int] | None = None
    resolved_sources: dict[int, dict] = {}
    if body.active_source_ids is not None:
        resolved = []
        for suuid in body.active_source_ids:
            source = db.get_aia_source(suuid)
            if source and source["workspace_id"] == workspace["id"]:
                resolved.append(source["id"])
                resolved_sources[source["id"]] = source
        source_ids = resolved if resolved else None

    # Routing + scope extraction — ONE combined query-understanding pre-call.
    # Routing picks GENERIC (cross-source overview) vs SPECIFIC (topic-focused hybrid
    # search); the scope part (Self-Query) turns any phrasing of an explicit
    # page/timestamp into a structured scope. Both jobs read the same question before
    # retrieval, so one round-trip carries both (was two parallel calls). The cheap
    # pre-filter still skips it when the route is obvious (popup, no sources, long
    # question) — then the regex fallback covers simple page refs.
    # PRE-CALL (re-activated): ONE LLM round-trip routes GENERIC (cross-source
    # overview) vs SPECIFIC (topic-focused) AND extracts any explicit page/time
    # scope (_understand_query). A cheap pre-filter skips it when the route is
    # obvious (popup / no sources / very long question) → SPECIFIC, no scope.
    # Routing drives: GENERIC → wide overview retrieval + overview system prompt;
    # SPECIFIC → neighbor-expansion retrieval; scope → exact page/time chunks.
    if _should_skip_intent_classification(body.source_text, source_ids, body.question):
        intent, scope_raw = "SPECIFIC", None
        logger.info("Chat: pre-call skipped → SPECIFIC ('{}' across {} sources)",
                    body.question[:60], len(source_ids or []))
    else:
        import time as _t_pc
        _t_pc0 = _t_pc.monotonic()
        intent, scope_raw = await _understand_query(llm, body.question)
        logger.info("Chat: pre-call routed intent={} scope={} in {:.1f}s ('{}' across {} sources)",
                    intent, scope_raw, _t_pc.monotonic() - _t_pc0, body.question[:60], len(source_ids or []))

    # The question is always used as-is: no conversation history is sent to the
    # LLM. Each turn is fully standalone (no follow-up condensing, no leaks).
    rewritten_question = body.question

    # Admin-tunable context budget (chars). Drives both the full-context-fits
    # check below and the final truncation in the shared context builder.
    context_budget = _context_budget()

    # ── Scoped path (Self-Query Retrieval) ──
    # An explicit page ("fasse Seite 5 zusammen") or media timestamp ("was wird bei
    # Minute 10 erzählt") is served from EXACTLY those chunks — not semantic search,
    # where the number is a poor token. The scope comes from the LLM extractor (any
    # phrasing/language); _parse_page_refs is a regex fallback for the skipped-pre-call
    # case (pages only). Scope applies to the FIRST selected source (others ignored —
    # it is ambiguous which document's "page 5"). Popups (source_text) keep their flow.
    scope_chunks: Optional[list[dict]] = None
    scope_requested = False
    if not body.source_text:
        unit = scope_raw["unit"] if scope_raw else None
        intervals = scope_raw["intervals"] if scope_raw else []
        # Regex fallback: if the pre-call (or the skipped-pre-call case) produced no
        # structured scope, still catch a simple "Seite 5" page reference in the text.
        if not intervals:
            rx = _parse_page_refs(body.question)
            if rx:
                unit, intervals = "page", [[p, p] for p in rx]
        if intervals:
            kind = _first_source_kind(source_ids, resolved_sources)  # "pdf"|"media"|None
            # Explicit page/time ask -> may short-circuit to can't-help when unservable.
            # "unknown" (bare numbers) only scopes opportunistically; if it can't, we
            # fall through to normal retrieval (the numbers might be content, not scope).
            explicit = unit in ("page", "time")
            scope_requested = explicit
            eff_unit = unit if explicit else (
                "page" if kind == "pdf" else "time" if kind == "media" else None)
            first_id = source_ids[0] if source_ids else None
            if first_id and eff_unit == "page" and kind == "pdf":
                max_page = max(db.get_source_page_numbers(first_id), default=None)
                if _page_scope_too_large(intervals, max_page, _MAX_PAGE_SPAN):
                    # Whole-/most-of-document range == an overview, not a precise scope.
                    # Route to GENERIC (multi-query overview) instead of scoping: the
                    # accuracy edge of scoping comes from a SMALL candidate set, and a
                    # huge range won't fit the context budget anyway. NOT unfulfillable.
                    intent = "GENERIC"
                    scope_requested = False
                    logger.info("Page scope too large (> {} pages) → routing to GENERIC overview", _MAX_PAGE_SPAN)
                else:
                    pages = _expand_page_intervals(intervals, max_page)
                    scope_chunks = _retrieve_page_scoped_context([first_id], pages)
                    logger.info("Page-scoped retrieval: pages {} → {} chunks (source={})",
                                pages, len(scope_chunks or []), first_id)
            elif first_id and eff_unit == "time" and kind == "media":
                media = db.get_aia_chunks_by_source(first_id)
                max_sec = max((c.get("end_time") or c.get("start_time") or 0 for c in media), default=None)
                ranges = _time_intervals_to_seconds(intervals, max_sec)
                scope_chunks = _retrieve_time_scoped_context(first_id, ranges)
                logger.info("Time-scoped retrieval: {} → {} chunks (source={})",
                            ranges, len(scope_chunks or []), first_id)
            else:
                logger.info("Scope requested (unit={}, kind={}) — not servable", unit, kind)

    # An explicit page/time scope was requested but cannot be served (wrong source
    # kind, or the page/minute does not exist). Falling back to semantic search yields
    # a misleading "topic not in sources" answer + wrong chips, so short-circuit with a
    # clear generic can't-help message — no LLM call, no retrieval. The genuine "no
    # info in sources" sentinel is reserved for real topic questions and stays.
    _cant_help = _scope_unfulfillable_message(scope_requested, scope_chunks, chat_lang)
    if _cant_help:
        logger.info("Scope request unfulfillable: generic can't-help message")

        async def _canned_stream() -> AsyncGenerator[str, None]:
            await asyncio.to_thread(
                db.save_aia_message, workspace["id"], user_id, "user", body.question,
                enrollment_id=enrollment_id,
            )
            yield f"data: {json.dumps({'qmap': [], 'source_pages': []})}\n\n"
            yield f"data: {json.dumps({'token': _cant_help})}\n\n"
            await asyncio.to_thread(
                db.save_aia_message, workspace["id"], user_id, "assistant", _cant_help,
                enrollment_id=enrollment_id,
            )
            yield f"data: {json.dumps({'done': True, 'answer': _cant_help, 'source_pages': [], 'source_qmap': []})}\n\n"

        return StreamingResponse(
            _canned_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ONE retrieval path now (SPECIFIC) plus a FIT-SHORTCUT — no GENERIC branch.
    # FIT-SHORTCUT: if the active sources fit the context budget, hand over the FULL
    # content (no retrieval, no embedding). Measured: fit-case = 10/10 and faster than
    # a retrieved sample. _full_context_if_fits short-circuits to None once over budget,
    # so a large source set bails after ~1-2 source fetches. Skipped for popups
    # (selection flow narrows to one source below). _specific_path stays False for the
    # fit-shortcut (single coherent window); it is set True only when we actually run
    # the per-source hybrid search, which is the only path that may need multi-call.
    _specific_path = False
    _fit_full = None if body.source_text else _full_context_if_fits(source_ids, context_budget)
    if scope_chunks:
        chunks = scope_chunks
    elif _fit_full is not None:
        chunks = _fit_full
        from collections import Counter
        _ps = Counter(c["source_id"] for c in chunks)
        logger.info("Fit-shortcut: {} chunks fit budget ({} chars), skipping retrieval | per-source: {}", len(chunks), context_budget, dict(_ps))
    elif intent == "GENERIC":
        # ── GENERIC overview retrieval: ONE wide hybrid search + round-robin coverage
        # across ALL active sources (not question-anchored), so the overview spans
        # every source/chapter; the overview system prompt below (_overview) then
        # drives document-by-document coverage. (Phase-2 note: per-source summaries
        # could replace this for many-chapter books — kept as chunks for now.)
        from src.services.aia_embeddings import get_embedding_provider
        provider = get_embedding_provider()
        chunks = await _retrieve_generic_context(
            provider, workspace["id"], source_ids, rewritten_question, budget=context_budget,
        )
    else:
        # ── Retrieval path: per-source hybrid + neighbor expansion (SPECIFIC) ──
        _specific_path = True
        from src.services.aia_embeddings import get_embedding_provider
        provider = get_embedding_provider()

        embed_text = body.source_text if body.source_text else rewritten_question
        # Run sync embedding call in a worker thread so a stalled provider
        # cannot block the FastAPI event loop.
        import asyncio as _asyncio
        query_vector = await _asyncio.to_thread(provider.embed_one, embed_text)

        # For popup actions, only search in the source file
        search_source_ids = source_ids
        if body.source_uuid:
            popup_source = db.get_aia_source(body.source_uuid)
            if popup_source:
                search_source_ids = [popup_source["id"]]

        # NEIGHBOR-CHUNK EXPANSION (single call). Plain top-K throws the tail away,
        # so a fact that sits NEXT TO a hit is lost (author "Thorsten Lübben" at
        # vec_rank ~645 — two chunks past the "Autoren" heading the search DOES
        # find). Instead we take the relevance ANCHORS (hybrid search) and pull each
        # anchor's document neighbours (±_NEIGHBOR_RADIUS): the answer almost always
        # sits beside something retrievable. Everything fits ONE coherent context
        # window, answered in a single call — a window can't be split, so it can't
        # grow a gap-filling hallucination (the earlier map-reduce "Prof. Böhm").
        #
        # SOURCE-level distance gate: drop a source only when its CLOSEST anchor is
        # off-topic (cosine > _DIST_FACTOR x global best). Single source → always kept.
        per_source_expanded: list[tuple[list[dict], Optional[float]]] = []
        for sid in search_source_ids:
            anchors = await _asyncio.to_thread(
                db.hybrid_search_chunks, workspace["id"], embed_text, query_vector,
                [sid], _NEIGHBOR_ANCHORS, fuzzy=True,  # typo-tolerant for the user query
            )
            if not anchors:
                continue
            _src_dists = [a["vec_distance"] for a in anchors if a.get("vec_distance") is not None]
            _src_best = min(_src_dists) if _src_dists else None
            doc = await _asyncio.to_thread(db.get_chunks_by_source, sid)
            per_source_expanded.append(
                (_expand_with_neighbors(anchors, doc, _NEIGHBOR_RADIUS, sid), _src_best)
            )
        _all_best = [d for _, d in per_source_expanded if d is not None]
        _global_best = min(_all_best) if _all_best else None
        _dist_threshold = _global_best * _DIST_FACTOR if _global_best is not None else None
        kept_expanded: list[list[dict]] = []
        for expanded, _src_best in per_source_expanded:
            if (len(per_source_expanded) > 1 and _dist_threshold is not None
                    and _src_best is not None and _src_best > _dist_threshold):
                logger.info("Per-source: source {} skipped off-topic (dist {:.3f} > {:.3f})",
                            expanded[0]["source_id"] if expanded else "?", _src_best, _dist_threshold)
                continue
            kept_expanded.append(expanded)
        # Cap to ONE context window: add neighbourhoods best-anchor-first until the
        # budget is full (the most on-point windows win), then re-sort survivors into
        # document order so each source reads as a coherent passage for the model.
        _flat = sorted((c for ex in kept_expanded for c in ex), key=lambda c: c.get("_anchor_dist", 1.0))
        chunks = []
        _used = 0
        for c in _flat:
            _len = len(c.get("content") or "")
            if chunks and _used + _len > context_budget:
                break
            chunks.append(c)
            _used += _len
        chunks.sort(key=lambda c: (
            c["source_id"],
            c.get("page_number") if c.get("page_number") is not None else -1,
            c.get("start_time") if c.get("start_time") is not None else -1.0,
            c.get("id") or 0,
        ))
        from collections import Counter as _Counter
        _per_src = _Counter(c["source_id"] for c in chunks)
        logger.info(
            "SPECIFIC neighbor-expansion: {} chunks ({} chars) from {} on-topic sources | per-source: {} | anchors<={} radius+-{} | Query: '{}'",
            len(chunks), _used, len(kept_expanded), dict(_per_src), _NEIGHBOR_ANCHORS, _NEIGHBOR_RADIUS, embed_text[:80],
        )

    # Single-page PDF scope ("fasse Seite 5 zusammen"): every line of the summary would
    # carry the SAME page chip for the page the user explicitly named — pure noise in
    # nav-only mode. We skip per-line attribution for it and append ONE click-to-page
    # anchor at the bottom (see finalize). Multi-page scope keeps per-line page chips
    # (they navigate); media scope keeps per-chunk timestamp chips.
    _scope_pages = {c["page_number"] for c in (scope_chunks or []) if c.get("page_number") is not None}
    scope_single_page = bool(scope_chunks) and len(_scope_pages) == 1

    # Build source-number mapping (Q1, Q2, ...) for multi-source disambiguation
    all_sources_list = {s["id"]: s for s in db.get_aia_sources_by_workspace(workspace["id"])}
    source_id_to_qnum: dict[int, int] = {}
    source_qmap: list[dict] = []  # [{qnum, uuid, filename}, ...]
    # Assign Q-numbers in the SAME order the source panel shows them — the
    # workspace source list is ordered created_at DESC (see
    # get_aia_sources_by_workspace), and this dict preserves that order. We walk
    # it and number only the sources that actually appear in chunks. This is both
    # STABLE (same active set -> same [N] every request, no longer dependent on
    # chunk/selection order) and intuitive ([N] matches the visible panel order).
    chunk_sids = {c["source_id"] for c in chunks}
    qnum_counter = 0
    for sid in all_sources_list:
        if sid not in chunk_sids:
            continue
        qnum_counter += 1
        source_id_to_qnum[sid] = qnum_counter
        src = all_sources_list[sid]
        source_qmap.append({
            "qnum": qnum_counter,
            "uuid": src["uuid"],
            "filename": src["filename"],
            "is_media": Path(src["filename"]).suffix.lower() in _MEDIA_EXTENSIONS,
        })
    # Defensive: a cited source not in the workspace list (shouldn't happen) still
    # needs a number so its citations aren't dropped. Append in first-seen order.
    for chunk in chunks:
        sid = chunk["source_id"]
        if sid not in source_id_to_qnum:
            qnum_counter += 1
            source_id_to_qnum[sid] = qnum_counter

    # Order round-robin: each source's Nth segment before any (N+1)th, so the
    # char-budget truncation below cuts late rounds and every source keeps its
    # early segments. SPECIFIC chunks carry no _seq -> grouped by panel order as
    # before. See _order_round_robin.
    chunks = _order_round_robin(chunks, source_id_to_qnum)

    # Pre-load Whisper segments for media sources so we can inject inline
    # (MM:SS) markers into each media chunk's context - lets the LLM cite
    # a precise timestamp within the chunk, not just the chunk start.
    transcript_by_source: dict[int, list[dict]] = {}
    for chunk in chunks:
        sid = chunk["source_id"]
        if chunk.get("start_time") is not None and sid not in transcript_by_source:
            src = all_sources_list.get(sid)
            if src:
                transcript_by_source[sid] = _load_transcript_segments(src)

    # Pack the retrieved chunks into ONE <documents> context window (XML tags per
    # chunk — Anthropic best practice). Every path is single-batch now: neighbor
    # expansion bounds SPECIFIC to one coherent window too, so there is no
    # map-reduce and no gap-filling hallucination. seen_pages_by_source is the set
    # of pages the model saw; the post-hoc attribution cross-check uses it to keep
    # a chip only on a page the model could actually have seen.
    batches, seen_pages_by_source = _pack_context_batches(
        chunks, context_budget, source_id_to_qnum, all_sources_list,
        transcript_by_source, multi=False,
    )
    context = batches[0] if batches else "<documents>\n\n</documents>"
    _ctx_chars = sum(len(b) for b in batches)
    logger.info(
        "Context: {} batch(es), {} chars total (~{} tokens), budget {}/batch | {} chunks",
        len(batches), _ctx_chars, round(_ctx_chars / 3.5), context_budget, len(chunks),
    )

    # Build the LLM call(s). One context window → one call (messages set here);
    # SPECIFIC overflow (multiple batches) → map-reduce, where _map_messages holds
    # one message pair per batch and the final reduce `messages` is built in
    # _stream after the map step. No conversation history is ever sent: each turn
    # is fully standalone (no follow-up condensing, no leaks).
    _map_messages: Optional[list[list[dict]]] = None
    messages: Optional[list[dict]] = None
    if body.source_text:
        # Popup actions: user has selected text themselves.
        page_ref = f" [S. {body.source_page}]" if body.source_page else ""
        # Only "Erklären"/Explain (simplify) needs the surrounding document context to
        # expand on the passage. Translate — and every other action — works on the
        # SELECTION ALONE: feeding it the doc context buries the "output ONLY the
        # translation" instruction and bloats the result with neighbouring material.
        # Identify the action by its KEY, not by list position: AIA_POPUP_ACTIONS[0]
        # used to be the explain action but is now "translate", so the old index check
        # silently swapped the two (translate got the context treatment, explain didn't).
        if body.action_key == "simplify":
            system_prompt = AIA_SYSTEM_DIRECT_WITH_CONTEXT
            user_message = f"{body.question}\n\nMarkierter Text (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}\n\nWeiterer Kontext aus dem Dokument:\n{context}"
        else:
            system_prompt = AIA_SYSTEM_DIRECT
            user_message = f"{body.question}\n\nText (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
    elif len(batches) <= 1:
        # OVERVIEW MODE only for a broad GENERIC ask (not a page/time SCOPE summary):
        # thematic lead-in + document-by-document coverage so all sources are touched.
        _overview = intent == "GENERIC" and not scope_chunks
        messages = [
            {"role": "system", "content": aia_system_rag(chat_lang, overview=_overview)},
            {"role": "user", "content": aia_rag_user_message(context, rewritten_question)},
        ]
    else:
        _map_messages = [
            [
                {"role": "system", "content": aia_system_rag(chat_lang)},
                {"role": "user", "content": aia_rag_user_message(b, rewritten_question)},
            ]
            for b in batches
        ]

    # Build source_pages before streaming so we can send them at the end
    source_pages: list[dict] = []
    is_popup = bool(body.source_text and body.source_uuid and body.source_page)

    # Build popup-selection entry up-front so the user message can carry it too
    # (lets the chat render the action chip + selection on reload, not just live).
    popup_entry: Optional[dict] = None
    if is_popup:
        popup_entry = {
            "source_uuid": body.source_uuid,
            "filename": body.source_filename or "",
            "page_number": body.source_page,
            "source_text": body.source_text,
            "is_popup_selection": True,
        }
        if body.action_key:
            action_def = next(
                (a for a in AIA_POPUP_ACTIONS if a["key"] == body.action_key),
                None,
            )
            if action_def:
                popup_entry["action_key"] = body.action_key
                popup_entry["action_icon"] = action_def["icon"]

    # Persist user question up-front so it survives any stream-termination path
    # (browser reload, CancelledError, yield exception). Otherwise a mid-stream
    # disconnect can leave the turn invisible after reload.
    await asyncio.to_thread(
        db.save_aia_message,
        workspace["id"], user_id, "user", body.question,
        source_pages=[popup_entry] if popup_entry else None,
        enrollment_id=enrollment_id,
    )

    if popup_entry:
        source_pages.append(popup_entry)
    else:
        all_sources = {s["id"]: s for s in db.get_aia_sources_by_workspace(workspace["id"])}
        for chunk in chunks:
            source = all_sources.get(chunk["source_id"])
            if source:
                raw = (chunk.get("content") or "").strip()
                raw = re.sub(r"^\d{1,3}\s+", "", raw).strip()
                # Skip leading partial word (chunk overlap can start mid-word)
                first_space = raw.find(" ")
                if first_space > 0 and first_space < 20:
                    raw = raw[first_space + 1:]
                snippet = raw[:400].strip()
                entry = {
                    "source_uuid": source["uuid"],
                    "filename": source["filename"],
                    "page_number": chunk["page_number"],
                    "source_text": snippet,
                }
                if chunk.get("start_time") is not None:
                    entry["start_time"] = chunk["start_time"]
                    entry["end_time"] = chunk.get("end_time")
                source_pages.append(entry)
        source_pages.sort(key=lambda x: x["page_number"])

    async def _stream() -> AsyncGenerator[str, None]:
        # Status is set to "error" on LLM failure, "aborted" when the client
        # disconnects mid-stream - default is "ok".
        _log_status = "ok"
        stream = None
        answer_parts: list[str] = []
        assistant_saved = False
        tokens_in: Optional[int] = None
        tokens_out: Optional[int] = None
        # Tokens spent by SPECIFIC map calls (the streamed reduce call's usage
        # overwrites tokens_in/out, so map usage is tracked separately and folded
        # into the usage log at the end). 0 for every single-call path.
        _map_tok_in = 0
        _map_tok_out = 0
        try:
            # Send qmap upfront so the frontend can resolve [Q1], [Q2] chips
            # during streaming instead of falling back to activeSourceIds[0].
            yield f"data: {json.dumps({'qmap': source_qmap, 'source_pages': source_pages})}\n\n"

            # Resolve the messages for the streamed (final) call. Single-call paths
            # (popup / one context batch) already have `messages`. SPECIFIC overflow
            # runs MAP first — answer every batch concurrently — then streams a
            # REDUCE over the partial answers, so no retrieved chunk is ever
            # truncated unseen (the whole point: a deep fact like an author name
            # cannot be cut). seen_pages_by_source (union across batches) is already
            # computed at pack time and feeds the post-hoc attribution cross-check.
            _final_messages = messages
            if _map_messages is not None:
                logger.info("SPECIFIC overflow: map-reduce over {} batches", len(_map_messages))

                async def _map_one(_msgs: list[dict]):
                    _r = await llm._async_client.with_options(
                        timeout=120.0, max_retries=0
                    ).chat.completions.create(
                        model=llm._model, messages=_msgs, temperature=0.2, stream=False,
                        **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
                    )
                    _txt = (_r.choices[0].message.content or "") if _r.choices else ""
                    _u = getattr(_r, "usage", None)
                    return (
                        _txt,
                        getattr(_u, "prompt_tokens", None) if _u else None,
                        getattr(_u, "completion_tokens", None) if _u else None,
                    )

                _map_out = await asyncio.gather(
                    *[_map_one(m) for m in _map_messages], return_exceptions=True
                )
                _partials: list[str] = []
                for _res in _map_out:
                    if isinstance(_res, Exception):
                        logger.warning("map call failed: {}", _res)
                        continue
                    _txt, _tin, _tout = _res
                    _map_tok_in += _tin or 0
                    _map_tok_out += _tout or 0
                    if _txt and _txt.strip():
                        _partials.append(_txt.strip())
                logger.info("map-reduce: {}/{} batches produced a partial answer",
                            len(_partials), len(_map_messages))
                if _partials:
                    _final_messages = [
                        {"role": "system", "content": aia_system_rag(chat_lang)},
                        {"role": "user", "content": aia_reduce_user_message(rewritten_question, _partials)},
                    ]
                else:
                    # Every map call empty/failed → single call over the first batch
                    # so the user still gets an answer rather than nothing.
                    _final_messages = [
                        {"role": "system", "content": aia_system_rag(chat_lang)},
                        {"role": "user", "content": aia_rag_user_message(context, rewritten_question)},
                    ]
            _line_buf = ""
            aborted = False
            # Safety net against a model repetition/degeneration loop (same few bullets
            # forever). When tripped we stop consuming the stream; the final dedup below
            # cleans the handful of repeats that streamed before the stop.
            _repeat_guard = _RepetitionGuard()
            _loop_detected = False
            try:
                # 90s connect/first-token timeout so an Ollama cold-start model
                # load can finish before we abort. Once tokens flow the
                # inter-chunk inactivity guard below takes over.
                stream = await llm._async_client.with_options(timeout=90.0, max_retries=0).chat.completions.create(
                    model=llm._model,
                    messages=_final_messages,
                    temperature=0.2,
                    stream=True,
                    # Ask for a final usage chunk so chat token counts land in
                    # usage_log + Langfuse. Providers that ignore it send no
                    # usage and _stream_usage_tokens just returns (None, None).
                    stream_options={"include_usage": True},
                    **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
                )
                # Inter-chunk inactivity guard: once streaming starts, the SDK's
                # request timeout no longer applies. If upstream goes silent
                # (zombie connection, provider stall) we'd wait forever and the
                # client's burst limit fills up with hung requests.
                _CHUNK_INACTIVITY_SECONDS = 60.0
                stream_iter = stream.__aiter__()
                while True:
                    try:
                        chunk_resp = await asyncio.wait_for(
                            stream_iter.__anext__(),
                            timeout=_CHUNK_INACTIVITY_SECONDS,
                        )
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        logger.warning(
                            "LLM stream inactive for {}s, aborting",
                            _CHUNK_INACTIVITY_SECONDS,
                        )
                        raise
                    if await request.is_disconnected():
                        aborted = True
                        break
                    _ti, _to = _stream_usage_tokens(chunk_resp)
                    if _ti is not None:
                        tokens_in = _ti
                    if _to is not None:
                        tokens_out = _to
                    delta = chunk_resp.choices[0].delta if chunk_resp.choices else None
                    if delta and delta.content:
                        answer_parts.append(delta.content)
                        yield f"data: {json.dumps({'token': delta.content})}\n\n"
                        _line_buf += delta.content
                        while "\n" in _line_buf:
                            _completed, _line_buf = _line_buf.split("\n", 1)
                            if _repeat_guard.is_loop(_completed):
                                logger.warning("Repetition loop detected, stopping stream")
                                _loop_detected = True
                                break
                    if _loop_detected:
                        break
            except Exception as e:
                _log_status = "error"
                logger.error("LLM stream error: {}", e)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return
            finally:
                if stream is not None:
                    try:
                        await stream.close()
                    except Exception:
                        pass

            _clean_answer = _dedup_repeated_lines(_sanitize_citations("".join(answer_parts).strip()))
            # Unified post-hoc attribution for every RAG answer (specific / generic / scope):
            # the model wrote plain text; we embed each substantial line, pgvector-search the
            # active sources, cross-check the hit against the pages actually retrieved into
            # context, and attach a nav-only chip. Popup/direct answers (their own selected
            # text + AIA_SYSTEM_DIRECT prompt) get no RAG attribution.
            if is_popup or not source_ids:
                answer = _clean_answer
            elif scope_single_page:
                # Single-page scope: skip per-line chips (they'd all repeat the named
                # page) and append ONE click-to-page anchor at the bottom.
                _aqn = source_id_to_qnum.get(scope_chunks[0]["source_id"]) if scope_chunks else None
                _apg = next(iter(_scope_pages), None)
                answer = _append_scope_anchor(_clean_answer, _aqn, _apg) if (_aqn and _apg is not None) else _clean_answer
            else:
                from src.services.aia_embeddings import get_embedding_provider
                _prov = get_embedding_provider()
                _stripped = _strip_inline_citation_chips(_clean_answer)  # defensive: model shouldn't emit chips now

                def _attribute_blocking() -> str:
                    # Batch-embed ALL candidate lines in ONE provider call (chunks into 100s
                    # internally) instead of one embed per line — same vectors, far fewer
                    # round-trips. search_one reuses the precomputed vector (per-line fallback).
                    _cands = [ln for ln in _stripped.split("\n") if _needs_attribution(ln)]
                    _vec_by_line: dict[str, list] = {}
                    if _cands:
                        try:
                            logger.info("post-hoc attribution: batch-embedding {} candidate lines in ONE call", len(_cands))
                            _vecs = _prov.embed(_cands)
                            if len(_vecs) == len(_cands):
                                _vec_by_line = dict(zip(_cands, _vecs))
                        except Exception as e:
                            logger.warning("post-hoc batch embedding failed, falling back per-line: {}", e)

                    def _search_one(_line: str):
                        try:
                            _qv = _vec_by_line.get(_line) or _prov.embed_one(_line)
                            return db.hybrid_search_chunks(workspace["id"], _line, _qv,
                                                           source_ids=source_ids, limit=4)
                        except Exception as e:
                            logger.warning("post-hoc attribution search failed for a line: {}", e)
                            return []

                    return _attribute_generic_text(_stripped, _search_one, source_id_to_qnum,
                                                   seen_pages_by_source=seen_pages_by_source,
                                                   # Exact-match grounding sees exactly what the
                                                   # model read (the single neighbor-expanded window).
                                                   context_chunks=chunks)

                answer = await asyncio.to_thread(_attribute_blocking)

            # Push the real question + answer onto the aia-chat trace; the
            # @observe decorator otherwise only captured the StreamingResponse.
            _enrich_chat_trace(
                _trace_id, body.question, answer,
                user_id=str(user_id), session_id=workspace_uuid,
            )

            if aborted:
                _log_status = "aborted"
                try:
                    langfuse_context.update_current_observation(
                        level="WARNING", status_message="client aborted stream"
                    )
                except Exception:
                    pass
                # Persist partial answer flagged as aborted so the rewriter can
                # filter it out and the UI can render a marker. User question
                # was already saved before _stream started.
                try:
                    await asyncio.to_thread(
                        db.save_aia_message,
                        workspace["id"], user_id, "assistant", answer,
                        source_pages=source_pages, enrollment_id=enrollment_id,
                        source_qmap=source_qmap, aborted=True,
                    )
                    assistant_saved = True
                except Exception as e:
                    logger.warning("Failed to persist aborted chat message: {}", e)
                return

            # Popup actions (translate / explain): append the source page as an inline
            # citation chip, exactly like normal RAG answers — the frontend renders it
            # as a [N] S. X pill inside the answer text (consistent with other answers),
            # and a click jumps to the page + re-highlights the user's exact selection.
            if is_popup:
                suffix = f" [S. {body.source_page}]"
                answer += suffix
                yield f"data: {json.dumps({'token': suffix})}\n\n"

            # Save assistant answer (user message was saved before _stream).
            await asyncio.to_thread(
                db.save_aia_message,
                workspace["id"], user_id, "assistant", answer,
                source_pages=source_pages, enrollment_id=enrollment_id,
                source_qmap=source_qmap,
            )
            assistant_saved = True

            # Send final metadata event - also send corrected answer
            yield f"data: {json.dumps({'done': True, 'answer': answer, 'source_pages': source_pages, 'source_qmap': source_qmap})}\n\n"
        finally:
            # Fallback: if no save path ran (CancelledError, yield exception on
            # dead connection, anything else that bypassed the explicit branches)
            # and we have any partial content, persist it as aborted. Use a sync
            # DB call so it survives task cancellation - asyncio.to_thread would
            # re-raise CancelledError here.
            if not assistant_saved and answer_parts:
                partial = "".join(answer_parts).strip()
                if partial:
                    try:
                        db.save_aia_message(
                            workspace["id"], user_id, "assistant", partial,
                            source_pages=source_pages, enrollment_id=enrollment_id,
                            source_qmap=source_qmap, aborted=True,
                        )
                        if _log_status == "ok":
                            _log_status = "aborted"
                    except Exception as e:
                        logger.warning("Fallback save of partial answer failed: {}", e)
            # Fold SPECIFIC map-call usage into the totals (the reduce stream's
            # usage already landed in tokens_in/out). `or None` keeps the
            # "no usage reported" case as None instead of a misleading 0.
            _total_in = ((tokens_in or 0) + _map_tok_in) or None
            _total_out = ((tokens_out or 0) + _map_tok_out) or None
            _log_usage(
                user_id=user_id,
                endpoint="chat",
                provider=getattr(llm, "_provider", None),
                model=getattr(llm, "_model", None),
                tokens_in=_total_in,
                tokens_out=_total_out,
                duration_ms=int((_time.monotonic() - _started_at) * 1000),
                status=_log_status,
            )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

