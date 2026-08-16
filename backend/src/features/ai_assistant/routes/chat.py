"""AI assistant routes - chat + RAG."""

import asyncio
import json
import re
import time
from bisect import bisect_left
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale, t
from src.limits import (
    AIA_CONTEXT_HARD_CAP,
    AIA_CONTEXT_MAX_CHARS,
    AIA_EMBED_QUERY_MAX_CHARS,
)
from src.services import model_limits
from src.security.rate_limit import enforce_burst
from src.security.usage_log import log_request as _log_usage
from src.tool_prompts import (
    AIA_SYSTEM_DIRECT,
    AIA_SYSTEM_DIRECT_WITH_CONTEXT,
    aia_system_rag,
    aia_rag_user_message,
    aia_reduce_user_message,
    AIA_POPUP_ACTIONS,
    AIA_INTENT_CLASSIFIER_SYSTEM,
    AIA_QUERY_UNDERSTANDING_SYSTEM,
    aia_query_understanding_system,
    is_gap_line,
    is_sentinel_refusal,
    refusal_reference_texts,
)
from . import _followup
from src.services.aia_adaptive_chat import (
    adaptive_chat_appendix,
    level_texts,
    seal_adaptive_suffix,
    DEFAULT_ADAPTIVE_BEHAVIOR,
    _LEGACY_ADAPTIVE_BEHAVIOR,
)
from src.services.aia_diagnosis_chat import ADAPTIVE_BEHAVIOR_SETTING
from src.services.aia_level_ladder import resolve_prompt_setting
from src.services.upstream_errors import upstream_error_code

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
# SPECIFIC budget TIERS (chars/source). At n≈30 the old flat 4000-char floor for EVERY
# source meant ~29 irrelevant laws × 4000 ≈ 116K chars of pure prefill ballast, and a
# loose co-dominant cutoff let a generic phrase ("schützt Artikel 1") tie 5-6
# structurally-similar laws that EACH grabbed ~50 chunks — so the context filled to
# 250K chars / ~71K tokens on essentially every question and the LLM was slow. Three
# tiers fix it without losing the answer (which lives in the closest source):
#   * PRIMARY (the single closest source) takes the weighted bulk — full coverage of
#     the law the question is actually about.
#   * SECONDARY co-dominant peers (a genuine 2-law / compare question) are each capped
#     so they can state their content without refilling the window with near-duplicates.
#   * FAR sources get ~1 top chunk: present for counting / compare-all, but no flood.
# _MAX_CODOMINANT bounds how many sources share the bulk (primary + secondaries).
_SPECIFIC_FAR_CHARS = 900         # far source: ~1 top chunk, just "present"
_SPECIFIC_SECONDARY_CHARS = 8000  # co-dominant non-primary source: ~10 chunks
_MAX_CODOMINANT = 4               # at most this many sources share the bulk
# Co-dominance cutoff for the SPECIFIC budget split: a source counts as "co-dominant"
# (and shares the bulk of the budget) only if its closest anchor is within this multiple
# of the globally best anchor. A single-target question ("welche Form schreibt das TVG
# vor") has ONE clearly-closest source → the other laws fall outside the cutoff and get
# only the floor, so they can't FLOOD the context and drown the answer (also cuts latency
# — far less context to chew). A genuine near-tie (AGG+BDSG cross-source) keeps BOTH inside
# the cutoff → budget split between them. Cosine-distance ratio → language-agnostic, no
# word lists. Tunable; loose enough that a real second source is never wrongly excluded
# (and the floor still represents it even if it is).
_CODOMINANT_FACTOR = 1.18
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
# Per-source retrieval (anchor search + chunk fetch) runs CONCURRENTLY — the queries are
# independent, and sequential they were ~0.8s at n=30. This semaphore caps in-flight DB
# queries BELOW the connection pool size (20) so parallel searches — and several
# concurrent chat requests sharing the pool — can never exhaust it. Shared per process.
_RETRIEVE_CONCURRENCY = 10
_retrieve_sem: Optional[asyncio.Semaphore] = None

# NAMED-SOURCE BOOST. A SPECIFIC question that names its document ("Was schützt das
# Grundgesetz?") must surface THAT source even when a distractor that merely CITES it
# (BKAG quotes "Artikel 1 GG", "Würde des Menschen" …) ranks closer to the query and
# would otherwise win the budget Primary slot. Fix is LANGUAGE-AGNOSTIC: every document
# names ITSELF in its title header (page 1: "Grundgesetz für die Bundesrepublik … GG").
# A long-enough question token that prefix-matches a word in EXACTLY ONE active source's
# title header marks the source the question names — generic words ("Gesetz", "Artikel")
# match many headers and are ignored, so it can never flood. The named source's distance
# is pulled just under the global best so the budget allocator makes it Primary.
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
    """Trim a RETRIEVAL query to AIA_EMBED_QUERY_MAX_CHARS before it is embedded.

    The question is embedded as ONE vector. A very long query produces a washed-out
    average vector (worse retrieval) and can overflow the embedding model's input
    limit — which is provider-configurable here (an admin may pick a 512-token
    model), so we cannot assume a high ceiling. Retrieval intent lives in the
    opening of a question, so a prefix is a fine search anchor. Only the SEARCH
    query is shortened; the FULL question still reaches the answer model."""
    if not text:
        return text
    return text[:AIA_EMBED_QUERY_MAX_CHARS]


def _title_word_match(token: str, hword: str) -> bool:
    """True if a question token names a source-title word (lang-agnostic, no wordlist).

    Three shapes, tuned to separate a real NAME from an incidental generic word:
      - exact:                token == hword                       ("grundgesetz")
      - name + law-type word: hword extends token by ≥4 chars      ("marke"→"markengesetz")
      - question inflection:  token extends hword by ≤3 chars       ("grundgesetzes"→"grundgesetz")
    The ≥4 vs ≤3 split is the crux: a real title compounds the typed name with a law-type
    word ("…gesetz", "…ordnung", "…act"); a false match only adds an inflection ("allgemeine"
    →"allgemeines", "stelle"→"stellen"), which this rejects.
    """
    if token == hword:
        return True
    # header = typed stem + a law-type word (≥4 chars). The stem must be substantial (≥7)
    # so a short common word can't prefix a law compound ("grund"→"grundgesetz").
    if len(token) >= 7 and hword.startswith(token) and len(hword) - len(token) >= 4:
        return True
    # question-side inflection of a substantial base name ("grundgesetzes"→"grundgesetz").
    if len(hword) >= 7 and token.startswith(hword) and len(token) - len(hword) <= 3:
        return True
    return False


def _named_source_ids(question: str, headers: dict[int, str]) -> set[int]:
    """Source ids the question NAMES, via discriminative self-title match (lang-agnostic).

    ``headers`` = {source_id: lowercased title region (page-1 header)}. A question token
    (len ≥ ``_NAME_MIN_TOKEN_LEN``) that ``_title_word_match``-es a word in EXACTLY ONE
    header marks that source as named. A token hitting several headers ("gesetz", "artikel")
    is generic and ignored, so this can only concentrate onto a uniquely-named source, never
    flood. A source whose copy is a fragment without its title page (no self-name in the
    header) simply isn't matched — we never invent a boost for missing content.
    """
    qtokens = {m.group(0).lower() for m in _NAME_TOKEN_RE.finditer(question or "")}
    if not qtokens or not headers:
        return set()
    hdr_words = {sid: set(_NAME_TOKEN_RE.findall(h or "")) for sid, h in headers.items()}
    named: set[int] = set()
    for t in qtokens:
        hits = [sid for sid, words in hdr_words.items()
                if any(_title_word_match(t, w) for w in words)]
        if len(hits) == 1:
            named.add(hits[0])
    return named


def _reserve_question_budget(budget: int, question: str) -> int:
    """Subtract the question's chars from the context char budget.

    The budget caps only the retrieved documents, but the question is appended
    AFTER the context in the answer prompt (aia_rag_user_message), so context +
    question could overflow the model window together. Reserve room for the
    question (plus a little prompt scaffolding) and floor at 1000 so even a tiny
    admin budget leaves usable context. Usually negligible against a 250k budget;
    it matters when an admin sets a small budget and a user pastes a long question."""
    return max(1000, budget - len(question or "") - 200)


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


def _servable_scope_intervals(unit: Optional[str], intervals: list[list]) -> list[list]:
    """Drop scope intervals that are almost certainly NOT a real page/time scope.

    A bare-number ("unknown") OPEN range — "ab 3", "from 3 on" — is overwhelmingly content
    or a date ("ab dritten Juli" → the model returns ``[[3, None]]``), not a page the user
    pointed at. Left in, it gets opportunistically mapped to a PDF page and the open end
    collapses to a single page (e.g. Seite 3), producing a misleading "not in the sources"
    answer scoped to the wrong page. So for ``unit="unknown"`` we keep only CLOSED ranges
    ("zwischen 12 und 13" → ``[[12, 13]]``), which carry a genuine "between X and Y" intent.
    An EXPLICIT page/time ask keeps ``unit`` "page"/"time" and is untouched (an open
    "ab Seite 10" stays a real scope)."""
    if unit != "unknown":
        return intervals
    return [iv for iv in intervals if iv[1] is not None]


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
            # Platz auch fuer ein Modell, dessen Denken sich nicht abstellen laesst.
            # Das Urteil wird ohnehin aus der Antwort herausgelesen.
            max_tokens=model_limits.PRECALL_MAX_TOKENS,
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


def _parse_understanding(content: str) -> tuple[str, dict, list[str]]:
    """Parse the combined query-understanding reply into
    ``(intent, scope, subqueries)``.

    Tolerant: strips <think>/code-fences, takes the first JSON object. ``intent``
    defaults to SPECIFIC (the conservative route); ``scope`` is validated by
    ``_parse_scope_response``; ``subqueries`` is the question split into its distinct
    asks for retrieval (empty when not decomposed / missing → caller uses the full
    question). If the JSON is broken we still salvage a GENERIC token if present. Any
    garbage → ``("SPECIFIC", {"unit": None, "intervals": []}, [])``."""
    import json
    raw = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    raw = raw.replace("```json", "").replace("```", "")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return "SPECIFIC", {"unit": None, "intervals": []}, []
    try:
        obj = json.loads(m.group(0))
    except Exception:
        cleaned = re.sub(r"[^A-Za-z]+", " ", raw).upper().split()
        return ("GENERIC" if "GENERIC" in cleaned else "SPECIFIC"), {"unit": None, "intervals": []}, []
    intent = "GENERIC" if "GENERIC" in str(obj.get("intent", "")).upper() else "SPECIFIC"
    scope_obj = obj.get("scope")
    scope = _parse_scope_response(json.dumps(scope_obj)) if scope_obj else {"unit": None, "intervals": []}
    subs_raw = obj.get("subqueries")
    subqueries = ([s.strip() for s in subs_raw if isinstance(s, str) and s.strip()][:3]
                  if isinstance(subs_raw, list) else [])
    return intent, scope, subqueries


async def _understand_query(
    llm, question: str, letzte_runde: Optional[dict] = None
) -> tuple[str, dict, list[str], str, str]:
    """ONE pre-call that does ALL query-understanding jobs in a single round-trip:
    route GENERIC vs SPECIFIC, extract any explicit page/time scope, split compound
    questions into subqueries, and — when ``letzte_runde`` is given — turn a follow-up
    into a self-contained question. Returns
    ``(intent, scope, subqueries, nachfrage_art, frage)`` where ``frage`` is the
    question retrieval should use (the original one unless it was rewritten).
    On any failure → ``("SPECIFIC", empty scope, [], KEINE, question)`` — the
    conservative route; the regex fallback still covers simple page refs downstream.
    Runs in a worker thread so a stalled provider cannot block the event loop."""
    import asyncio
    def _call():
        # 60s covers Ollama cold-start; warm calls return in ~500ms.
        return llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system",
                 "content": aia_query_understanding_system(bool(letzte_runde))},
                {"role": "user", "content": _followup.vorcall_eingabe(question, letzte_runde)},
            ],
            temperature=0.0,
            # Platz fuer die Teilfragen einer zusammengesetzten Frage, und fuer ein
            # Modell, dessen Denken sich nicht abstellen laesst.
            max_tokens=model_limits.PRECALL_MAX_TOKENS,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
    try:
        response = await asyncio.to_thread(_call)
        msg = response.choices[0].message
        raw = msg.content or getattr(msg, "reasoning_content", None) or ""
    except Exception as e:
        logger.warning("Query understanding failed, defaulting to SPECIFIC/no-scope: {}", e)
        return "SPECIFIC", {"unit": None, "intervals": []}, [], _followup.KEINE, question
    intent, scope, subqueries = _parse_understanding(raw)
    art, frage = (_followup.nachfrage_lesen(raw, question) if letzte_runde
                  else (_followup.KEINE, question))
    logger.info("Query understanding: '{}' → intent={} scope={} subqueries={} nachfrage={} frage='{}'",
                question[:50], intent, scope, subqueries, art, frage[:60])
    return intent, scope, subqueries, art, frage


def _context_budget() -> int:
    """Zeichenbudget fuer den Kontext, admin-einstellbar ueber ``aia_context_max_chars``.

    KIS laeuft auf sehr verschiedenen Aufbauten, von einem lokalen Ollama bis zu einem
    grossen Cloud-Modell, deshalb ist die Zahl einstellbar. Sie wird nur dann gekuerzt,
    wenn ueber das Modell nachweislich bekannt ist, dass es weniger vertraegt, sonst
    kostet ein zu hoch eingetragener Wert bei JEDER Anfrage einen Fehlversuch.

    Dieselbe Rechnung wie bei den Werkzeugen, deshalb steht sie nur einmal in
    ``tasks._context_budget`` und wird hier nur weitergereicht.
    """
    from src.features.ai_assistant.tasks._context_budget import context_budget
    return context_budget()


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
    # Cap the retrieval query (embed + lexical search). Long pastes overflow the
    # embedding model / blur the vector; the full question still reaches the answer.
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

    # Absolute fallback: retrieval returned nothing (e.g. media with no matchable
    # text). Hand over an even-spread sample of raw chunks so the LLM still sees
    # the document; the char budget at the call site truncates the rest.
    if not chunks:
        for sid in source_ids or []:
            _raw = await asyncio.to_thread(db.get_aia_chunks_by_source, sid)
            chunks.extend(_sample(_raw, _GENERIC_FALLBACK_SAMPLE))
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
    """Relevance-CONCENTRATED, TIERED per-source chunk budget for SPECIFIC.

    ``kept`` = the kept sources as ``(hits, src_best_distance)`` pairs, ``hits``
    already ordered most-relevant-first. One char budget is split by relevance so a
    single-target question is never flooded — and, crucially, never *bloated* — by
    the other active sources:

    - **Primary** — the single closest source — takes the weighted bulk (full
      coverage of the law the question is about). A single source gets the lot.
    - **Secondary** co-dominant peers (closest anchor within ``_CODOMINANT_FACTOR`` ×
      the global best, AND among the nearest ``_MAX_CODOMINANT``) are each capped at
      ``_SPECIFIC_SECONDARY_CHARS`` — enough to answer a genuine 2-law / compare
      question, not enough to refill the window with near-duplicates of the primary.
    - **Far** sources (outside the cutoff, or beyond ``_MAX_CODOMINANT``) get only
      ``_SPECIFIC_FAR_CHARS`` (≈ one top chunk) — present for counting / compare-all
      questions, but unable to flood (or bloat) the context.

    Why tiers: at scale (n≈30) a loose cutoff ties many structurally-similar docs and
    a flat floor for each turned EVERY question into a ~250k-char / ~71k-token context
    — slow, for an answer that lives in ONE source. Slack is never redistributed to
    less-relevant docs (that would re-introduce the flood). Total stays ≤ char_budget.
    """
    if not kept:
        return []
    if len(kept) == 1:
        return _take_chunks_within(kept[0][0], char_budget)

    dists = [d for _, d in kept if d is not None]
    best = min(dists) if dists else None
    cutoff = best * _CODOMINANT_FACTOR if best is not None else None

    # Nearest first: rank 0 is the PRIMARY; co-dominant peers ride along only up to
    # _MAX_CODOMINANT, everyone else is FAR. (None distance sorts last → treated far
    # unless it lands in the first _MAX_CODOMINANT slots as a safe fallback.)
    ordered = sorted(kept, key=lambda hd: hd[1] if hd[1] is not None else float("inf"))
    far_cap = min(_SPECIFIC_FAR_CHARS, char_budget // len(kept))

    out: list[dict] = []
    pool: list[tuple[list[dict], Optional[float], int]] = []  # (hits, dist, rank)
    for rank, (hits, d) in enumerate(ordered):
        codominant = cutoff is None or d is None or d <= cutoff
        if rank < _MAX_CODOMINANT and (rank == 0 or codominant):
            pool.append((hits, d, rank))
        else:
            out.extend(_take_chunks_within(hits, far_cap))  # far source: ~1 chunk

    # Remaining budget after the far sources, split among the bulk pool by closeness.
    far_count = len(ordered) - len(pool)
    remaining = max(0, char_budget - far_cap * far_count)
    weights = [(best / d if (best and d) else 1.0) for _h, d, _r in pool]
    wsum = sum(weights) or float(len(pool))
    for (hits, _d, rank), w in zip(pool, weights):
        share = int(remaining * w / wsum)
        if rank > 0:
            share = min(share, _SPECIFIC_SECONDARY_CHARS)  # secondary: capped
        out.extend(_take_chunks_within(hits, max(share, far_cap)))
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
    order, each tagged with ``_anchor_dist`` — the distance of the anchor that chunk
    actually sits NEAREST to — so the caller can trim best-first.

    Why: a fact often sits NEXT TO a hit, or BETWEEN two hits, rather than in either
    (a co-author named between the "Autoren" heading and the contact section). The
    window + bridge catches it in a single coherent call — no whole-document read.

    Why PER CHUNK and not per span. Until 2026-08-16 a merged span handed its single
    best distance to every chunk in it. On a long PDF that is harmless (24 anchors do
    not cover 500 chunks, so several spans with distinct distances survive). On a
    lecture transcript of 14-31 chunks the anchors cover the WHOLE document and merge
    into ONE span: every chunk scored equal, ``sorted(key=_anchor_dist)`` in the
    caller became a no-op, and the per-source budget then cut the transcript from the
    FRONT — the greeting instead of the answer. Measured on a real 13-recording
    workspace: 4 of 10 eval cases were found by the search at rank 1-9 and thrown
    away here (``scripts/rag_retrieval_eval.py``).

    Distance to the nearest anchor, ties to the better distance. Bridge-filler chunks
    are covered by the same rule, so a bridge cannot smuggle weak material in at a
    good score.
    """
    pos = {c["id"]: i for i, c in enumerate(doc_chunks)}
    n = len(doc_chunks)
    # (index, distance) per anchor, sorted by index — the input for both the windows
    # below and the per-chunk nearest-anchor lookup.
    marks: list[tuple[int, float]] = []
    for a in anchors:
        i = pos.get(a["id"])
        if i is None:
            continue
        ad = a.get("vec_distance")
        marks.append((i, ad if ad is not None else 1.0))
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

    def _nearest(j: int) -> float:
        """Distance of the anchor closest to chunk index ``j``, ties to the better one.

        bisect over the sorted anchor indices, so only the two neighbouring anchors
        are compared instead of all of them — the whole expansion stays linear in the
        number of covered chunks even at 24 anchors per source."""
        k = bisect_left(mark_idx, j)
        best: Optional[tuple[int, float]] = None
        for cand in (k - 1, k):
            if 0 <= cand < len(marks):
                gap = abs(marks[cand][0] - j)
                key = (gap, marks[cand][1])
                if best is None or key < best:
                    best = key
        return best[1] if best else 1.0

    out: list[dict] = []
    for lo, hi in spans:
        for j in range(lo, hi + 1):
            c = dict(doc_chunks[j])
            c["source_id"] = source_id
            c["_anchor_dist"] = _nearest(j)
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
    """The SPECIFIC retrieval path: per-source hybrid anchors + neighbour expansion.

    Extracted from :func:`chat` so the retrieval EVAL harness
    (``scripts/rag_retrieval_eval.py``) exercises the exact code that ships,
    instead of a copy that silently drifts. Pure retrieval: no request object, no
    streaming, no LLM — it takes the already-resolved queries and returns the
    chunks that go into the prompt, in document order per source.
    """
    # Cap each retrieval query (embed + lexical search) — see _truncate_query_for_embedding.
    _retrieval_queries = [_truncate_query_for_embedding(q) for q in retrieval_queries]
    _qvecs = await asyncio.to_thread(provider.embed, _retrieval_queries)
    _query_pairs = list(zip(_retrieval_queries, _qvecs))

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
    # No trigram fuzzy here: it is a no-index per-row word_similarity scan (~3s/call,
    # the n=30 latency killer) and vector search is already typo-robust at the
    # SEMANTIC level (embeddings put "authoren" next to "Autoren"), with BM25 + ILIKE
    # covering exact tokens. So the per-source anchor search runs WITHOUT fuzzy
    # (~0.01s each). And since the sources are independent, the searches run
    # CONCURRENTLY (semaphore-bounded), turning ~0.8s sequential into ~0.15s at n=30.
    _sem = _get_retrieve_sem()

    async def _expand_one(sid: int) -> Optional[tuple[list[dict], Optional[float], str]]:
        async with _sem:
            # Search this source with EACH retrieval query (clause); merge anchors,
            # keeping each chunk's BEST (smallest) distance across the clauses.
            merged: dict[int, dict] = {}
            for _qtext, _qvec in _query_pairs:
                for a in (await asyncio.to_thread(
                        db.hybrid_search_chunks, workspace_id, _qtext, _qvec,
                        [sid], _NEIGHBOR_ANCHORS, fuzzy=False) or []):
                    ad = a.get("vec_distance")
                    prev = merged.get(a["id"])
                    if prev is None or (ad is not None and (prev.get("vec_distance") is None
                                                            or ad < prev["vec_distance"])):
                        merged[a["id"]] = a
            if not merged:
                return None
            doc = await asyncio.to_thread(db.get_chunks_by_source, sid)
        anchors = list(merged.values())
        _sd = [a["vec_distance"] for a in anchors if a.get("vec_distance") is not None]
        _hdr = ((doc[0].get("content") if doc else None) or "")[:_NAME_TITLE_CHARS].lower()
        return (_expand_with_neighbors(anchors, doc, _NEIGHBOR_RADIUS, sid),
                min(_sd) if _sd else None, _hdr)

    _results = await asyncio.gather(*[_expand_one(s) for s in search_source_ids])
    per_source_expanded: list[tuple[list[dict], Optional[float], str]] = [
        r for r in _results if r is not None
    ]
    _all_best = [d for _, d, _h in per_source_expanded if d is not None]
    _global_best = min(_all_best) if _all_best else None
    logger.info("Retrieval relevance: global best cosine distance {} over {} sources",
                f"{_global_best:.3f}" if _global_best is not None else "n/a",
                len(per_source_expanded))
    _dist_threshold = _global_best * _DIST_FACTOR if _global_best is not None else None
    # Title header (page-1 self-name) per source — input to the named-source boost below.
    _headers = {exp[0]["source_id"]: hdr for exp, _d, hdr in per_source_expanded if exp}
    # Hard drop-gate (off by default at _DIST_FACTOR=999) — kept as a safety net.
    # The SOFT concentration below is what actually stops the multi-source flood.
    kept: list[tuple[list[dict], Optional[float]]] = []
    for expanded, _src_best, _hdr in per_source_expanded:
        if (len(per_source_expanded) > 1 and _dist_threshold is not None
                and _src_best is not None and _src_best > _dist_threshold):
            logger.info("Per-source: source {} skipped off-topic (dist {:.3f} > {:.3f})",
                        expanded[0]["source_id"] if expanded else "?", _src_best, _dist_threshold)
            continue
        # order each source's windows best-anchor-first so its budget share takes
        # the most on-point chunks first
        kept.append((sorted(expanded, key=lambda c: c.get("_anchor_dist", 1.0)), _src_best))
    # NAMED-SOURCE BOOST: if the question uniquely names a source by its title
    # (self-name match), pull that source's distance just under the global best so the
    # allocator below makes it Primary — a distractor that merely CITES it can no longer
    # steal the bulk. No-op when nothing is uniquely named or a single source is active.
    if len(kept) > 1 and _global_best is not None:
        _named = _named_source_ids(question, _headers)
        if _named:
            _nd = _global_best * _NAME_BOOST_FACTOR
            kept = [
                (hits, (_nd if (hits and hits[0]["source_id"] in _named
                                and (d is None or _nd < d)) else d))
                for hits, d in kept
            ]
            logger.info("SPECIFIC named-source boost → sources {} → Primary (dist {:.3f})",
                        sorted(_named), _nd)
    # RELEVANCE-CONCENTRATED budget split: the source(s) closest to the query get
    # the bulk, far sources only a floor — a single-target question is no longer
    # flooded by unrelated laws (which also keeps context + latency small). See
    # _allocate_specific_budget. Then re-sort into document order so each source
    # reads as a coherent passage for the model.
    chunks = _allocate_specific_budget(kept, char_budget)
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
        "SPECIFIC neighbor-expansion: {} chunks ({} chars) from {} kept sources | per-source: {} | anchors<={} radius+-{} | Query: '{}'",
        len(chunks), _used, len(kept), dict(_per_src), _NEIGHBOR_ANCHORS, _NEIGHBOR_RADIUS,
        (_retrieval_queries[0] if _retrieval_queries else "")[:80],
    )
    return chunks


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
    _format_timestamp,
    _load_transcript_segments,
    _enrich_media_content,
    _RepetitionGuard,
    _tail_repeats,
    _collapse_repeats,
    _dedup_repeated_lines,
    _strip_source_list,
    _strip_tiny_tables,
    _strip_inline_citation_chips,
    _attribute_generic_text,
    _needs_attribution,
    _attribution_subunits,
    _parallel_search,
    _AttributionPrewarmer,
    _refusal_lines,
    is_refusal_answer,
    _append_scope_anchor,
    _MEDIA_EXTENSIONS,
    _sanitize_citations,
    _strip_arrow_connectors,
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
    _user_settings = db.get_aia_user_settings(workspace["id"], user_id) or {}
    chat_lang = _user_settings.get("chat_lang", "de")

    # Adaptive tutor behaviour is coupled to the Sprachtrainer: answers are only
    # CEFR-pitched where the owner released the trainer AND the reader switched it
    # on for themselves. Everywhere else they stay plain. The CEFR level is stored
    # globally per user, so this per-workspace gate is also what stops it leaking
    # into other workspaces, and the personal one keeps someone who turned the
    # trainer off from getting level-pitched answers anyway.
    _adaptive_suffix, _applied_level = "", None
    if db.is_language_training_active(workspace["id"]) and _user_settings.get("language_training_active", False):
        # A learner with a stored CEFR level gets answers pitched at that level,
        # calibrated with the description and a sample of that level's language
        # (the same Stufen-Leiter the diagnosis places learners with). Empty
        # setting or no level -> no change. Computed once here; appended to the
        # USER message in each path below, right next to the question, which is
        # where the model weights it most.
        _level = db.get_user_language_level(user_id)["language_level"]
        _example, _description = level_texts(_level)
        _adaptive_suffix, _applied_level = adaptive_chat_appendix(
            _level,
            resolve_prompt_setting(
                db.get_setting(ADAPTIVE_BEHAVIOR_SETTING, ""),
                _LEGACY_ADAPTIVE_BEHAVIOR,
                DEFAULT_ADAPTIVE_BEHAVIOR,
            ),
            _example,
            _description,
        )

    # Sealed OUTSIDE the trainer gate: the sources guard goes out on every chat, with
    # or without the adaptive block, and seal_adaptive_suffix keeps it LAST.
    _adaptive_suffix = seal_adaptive_suffix(_adaptive_suffix)

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
    # FOLLOW-UP: the last completed round rides along in the SAME pre-call, so a
    # short "erkläre genauer" / "in 3 Stichpunkten" can be made self-contained
    # BEFORE retrieval (see routes/_followup). It is looked up only when the
    # pre-call actually runs and the question is short enough to be a follow-up,
    # and it only reaches the model when that round really carries context.
    # Still no history in the ANSWER call.
    _letzte_runde = None
    if _should_skip_intent_classification(body.source_text, source_ids, body.question):
        intent, scope_raw, subqueries = "SPECIFIC", None, []
        _nachfrage, rewritten_question = _followup.KEINE, body.question
        logger.info("Chat: pre-call skipped → SPECIFIC ('{}' across {} sources)",
                    body.question[:60], len(source_ids or []))
    else:
        import time as _t_pc
        _t_pc0 = _t_pc.monotonic()
        if _followup.lohnt_nachschlagen(body.question, body.source_text):
            _letzte_runde = await asyncio.to_thread(
                db.get_last_aia_round, workspace["id"], user_id, enrollment_id)
            if not _followup.ist_nachfrage_moeglich(
                    body.question, _letzte_runde, body.source_text):
                _letzte_runde = None
        intent, scope_raw, subqueries, _nachfrage, rewritten_question = await _understand_query(
            llm, body.question, _letzte_runde)
        logger.info("Chat: pre-call routed intent={} scope={} subqueries={} nachfrage={} in {:.1f}s ('{}' across {} sources)",
                    intent, scope_raw, len(subqueries), _nachfrage, _t_pc.monotonic() - _t_pc0, body.question[:60], len(source_ids or []))

    # Reshaping the last answer ("in 3 Stichpunkten", "kürzer"): there is nothing
    # to search for — the material IS that answer. Retrieval, scope and context
    # are skipped below; the citation chips of that round are carried over, so the
    # reshaped answer points at exactly the passages the original one did.
    _umformen = _nachfrage == _followup.UMFORMEN and bool(_letzte_runde)
    if _umformen:
        logger.info("Chat: Folgefrage formt die letzte Antwort um ('{}'), keine Suche",
                    body.question[:60])
    elif _nachfrage == _followup.UMSCHREIBEN:
        logger.info("Chat: Folgefrage eigenstaendig gemacht: '{}' → '{}'",
                    body.question[:60], rewritten_question[:80])

    # Admin-tunable context budget (chars). Drives both the full-context-fits
    # check below and the final truncation in the shared context builder. Reserve
    # room for the question: the budget caps the retrieved DOCUMENTS, but the
    # question is appended AFTER them in the answer prompt, so context + question
    # must fit the model window together (see _reserve_question_budget).
    context_budget = _reserve_question_budget(_context_budget(), body.question)

    # ── Scoped path (Self-Query Retrieval) ──
    # An explicit page ("fasse Seite 5 zusammen") or media timestamp ("was wird bei
    # Minute 10 erzählt") is served from EXACTLY those chunks — not semantic search,
    # where the number is a poor token. The scope comes from the LLM extractor (any
    # phrasing/language); _parse_page_refs is a regex fallback for the skipped-pre-call
    # case (pages only). Scope applies to the FIRST selected source (others ignored —
    # it is ambiguous which document's "page 5"). Popups (source_text) keep their flow.
    scope_chunks: Optional[list[dict]] = None
    scope_requested = False
    if not body.source_text and not _umformen:
        unit = scope_raw["unit"] if scope_raw else None
        intervals = scope_raw["intervals"] if scope_raw else []
        # Drop a bare-number OPEN range ("ab dritten Juli" → unit="unknown", [[3, None]]):
        # it is a date/content, not a page — left in it would scope a PDF to the wrong page.
        intervals = _servable_scope_intervals(unit, intervals)
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
    _fit_full = (None if (body.source_text or _umformen)
                 else _full_context_if_fits(source_ids, context_budget))
    if _umformen:
        # Kein Suchtreffer, kein Kontext: der Stoff ist die letzte Antwort selbst
        # (die Nachrichten dafuer werden weiter unten gebaut).
        chunks = []
    elif scope_chunks:
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
        # COMPOUND-question decomposition: a question that asks about several distinct
        # things ("X und Y") is searched per CLAUSE, so a secondary source is anchored by
        # the clause that concerns it. Without this the dominant clause's embedding hides
        # the other source's relevant chunks → the model answers that part from the wrong
        # pages or hallucinates (and the post-hoc chip then correctly refuses to cite it).
        # Single-target questions / popup text keep exactly ONE query → identical to before.
        _retrieval_queries = (subqueries if (len(subqueries) > 1 and not body.source_text)
                              else [embed_text])

        # For popup actions, only search in the source file
        search_source_ids = source_ids
        if body.source_uuid:
            popup_source = db.get_aia_source(body.source_uuid)
            if popup_source:
                search_source_ids = [popup_source["id"]]

        chunks = await _retrieve_specific_context(
            provider, workspace["id"], search_source_ids,
            _retrieval_queries, rewritten_question, context_budget,
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

    # Beim Umformen gibt es keine Treffer, aus denen Nummern und gesehene Seiten
    # entstehen koennten. Beides kommt aus der Runde, die umgeformt wird: die
    # Aussage bleibt dieselbe, also bleiben auch die Stellen dieselben.
    _umform_seiten: list[dict] = []
    if _umformen:
        _uuid_zu_id = {s["uuid"]: sid for sid, s in all_sources_list.items()}
        source_qmap, source_id_to_qnum, _umform_gesehen, _umform_seiten = _followup.letzte_quellen(
            _letzte_runde, _uuid_zu_id)

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
    if _umformen:
        seen_pages_by_source = _umform_gesehen
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
    # Language anchor: a question without a language of its own ("hi", "klsdf")
    # would otherwise be answered in the system prompt's own language (English)
    # and the chat flips mid-conversation. Read BEFORE this turn is persisted
    # below, so it really is the PREVIOUS question. Empty -> chat_lang decides.
    # Popups carry their own selected text, so they skip the lookup.
    _prev_questions = [] if body.source_text else db.get_last_aia_user_questions(
        workspace["id"], user_id, enrollment_id=enrollment_id)
    if _umformen:
        # Umformen der letzten Antwort: eigener Prompt, kein <documents>-Kontext.
        # Die Anweisung ist die eigenstaendig gemachte Zeile aus dem Vor-Call
        # ("Fasse die Pruefungsleistung in 3 kurzen Stichpunkten zusammen").
        messages = _followup.umform_nachrichten(
            _letzte_runde, rewritten_question, chat_lang, _prev_questions, _adaptive_suffix)
    elif body.source_text:
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
            {"role": "user", "content": user_message + _adaptive_suffix},
        ]
    elif len(batches) <= 1:
        # OVERVIEW MODE only for a broad GENERIC ask (not a page/time SCOPE summary):
        # thematic lead-in + document-by-document coverage so all sources are touched.
        _overview = intent == "GENERIC" and not scope_chunks
        messages = [
            {"role": "system", "content": aia_system_rag(chat_lang, overview=_overview, prev_questions=_prev_questions)},
            {"role": "user", "content": aia_rag_user_message(context, rewritten_question, _prev_questions) + _adaptive_suffix},
        ]
    else:
        _map_messages = [
            [
                {"role": "system", "content": aia_system_rag(chat_lang, prev_questions=_prev_questions)},
                {"role": "user", "content": aia_rag_user_message(b, rewritten_question, _prev_questions) + _adaptive_suffix},
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

    if _umformen:
        # Dieselben Stellen wie in der Runde, die umgeformt wird.
        source_pages = list(_umform_seiten)
    elif popup_entry:
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
        # B2 prewarm (set up before the stream loop when the RAG-attribution path applies);
        # declared here so the outer finally can always cancel a still-running pump.
        _prewarmer = None
        _pump_task = None
        _pump_stop = None
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
            yield f"data: {json.dumps({'qmap': source_qmap, 'source_pages': source_pages, 'applied_level': _applied_level})}\n\n"

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
                        {"role": "system", "content": aia_system_rag(chat_lang, prev_questions=_prev_questions)},
                        {"role": "user", "content": aia_reduce_user_message(rewritten_question, _partials) + _adaptive_suffix},
                    ]
                else:
                    # Every map call empty/failed → single call over the first batch
                    # so the user still gets an answer rather than nothing.
                    _final_messages = [
                        {"role": "system", "content": aia_system_rag(chat_lang, prev_questions=_prev_questions)},
                        {"role": "user", "content": aia_rag_user_message(context, rewritten_question, _prev_questions) + _adaptive_suffix},
                    ]
            _line_buf = ""
            aborted = False
            # Safety net against a model repetition/degeneration loop (same few bullets
            # forever). When tripped we stop consuming the stream; the final dedup below
            # cleans the handful of repeats that streamed before the stop.
            _repeat_guard = _RepetitionGuard()
            _loop_detected = False
            # Intra-line loop guard baseline: the line guard only fires on a COMPLETED
            # line (\n); a phrase looped with no newline never completes one, so we also
            # scan the growing buffer's tail every _INTRA_LINE_CHECK_EVERY chars.
            _last_intra = 0
            _INTRA_LINE_CHECK_EVERY = 1500
            # B2: warm the post-hoc attribution caches WHILE the answer streams. Only for the
            # RAG-attribution path (source_ids, not popup, not single-page scope — exactly the
            # `else` branch that runs _attribute_blocking). A background pump embeds+searches
            # completed lines every ~0.35s so that when streaming ends most work is already
            # cached; the final attribution then only computes the misses.
            _do_prewarm = bool(source_ids) and not is_popup and not scope_single_page
            if _do_prewarm:
                from src.services.aia_embeddings import get_embedding_provider as _get_ep
                from src.limits import AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS
                # Kurze Schranke, kein zweiter Versuch: das Vorwaermen ist eine Abkuerzung.
                # Antwortet die Gegenstelle nicht, soll es das schnell merken und den Weg
                # freigeben, statt Threads an einer haengenden Anfrage zu binden.
                _pw_prov = _get_ep(timeout=AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS,
                                   retry_on_timeout=False)

                def _pw_search(_ln, _vec):
                    try:
                        return db.hybrid_search_chunks(
                            workspace["id"], _ln, _vec or _pw_prov.embed_one(_ln),
                            source_ids=source_ids, limit=10)
                    except Exception:
                        return []

                _prewarmer = _AttributionPrewarmer(_pw_prov.embed, _pw_search)
                _pump_stop = asyncio.Event()

                async def _prewarm_pump():
                    # Throttle for the SHARED embed budget (GWDG ~2/s, 15/min across the whole
                    # university): flush at most every _PREWARM_POLL_SECONDS and at most
                    # _PREWARM_MAX_FLUSHES times while streaming, so prewarm adds only a handful
                    # of spaced embed calls per answer (not one-per-line). Whatever is still
                    # pending after the cap is embedded once by the final attribution. These two
                    # constants are the throttle knobs — dial down under heavier concurrency.
                    _PREWARM_POLL_SECONDS = 2.0
                    _PREWARM_MAX_FLUSHES = 6
                    while not _pump_stop.is_set():
                        try:
                            await asyncio.wait_for(_pump_stop.wait(), timeout=_PREWARM_POLL_SECONDS)
                        except asyncio.TimeoutError:
                            pass
                        if _pump_stop.is_set():
                            break
                        if _prewarmer.flushes < _PREWARM_MAX_FLUSHES and _prewarmer.pending_count():
                            try:
                                await _prewarmer.flush()
                            except Exception:
                                pass
                    await _prewarmer.flush()  # final drain of whatever is still pending

                _pump_task = asyncio.create_task(_prewarm_pump())
            async def _open_stream(messages):
                # 90s connect/first-token timeout so an Ollama cold-start model
                # load can finish before we abort. Once tokens flow the
                # inter-chunk inactivity guard below takes over.
                return await llm._async_client.with_options(timeout=90.0, max_retries=0).chat.completions.create(
                    model=llm._model,
                    messages=messages,
                    temperature=0.2,
                    stream=True,
                    # Ask for a final usage chunk so chat token counts land in
                    # usage_log + Langfuse. Providers that ignore it send no
                    # usage and _stream_usage_tokens just returns (None, None).
                    stream_options={"include_usage": True},
                    **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
                )

            try:
                try:
                    stream = await _open_stream(_final_messages)
                except Exception as _limit_err:  # noqa: BLE001
                    # Der Anbieter lehnt zu viel Kontext ab, BEVOR ein Zeichen geflossen
                    # ist. Nennt seine Absage die Fenstergroesse, merken wir sie uns,
                    # kuerzen und senden sofort nochmal. Der Nutzer sieht eine kurze
                    # Verzoegerung statt eines Fehlers, und beim naechsten Mal passt es
                    # von vornherein. Nennt sie keine, bleibt es beim Fehler wie bisher.
                    _fenster = model_limits.learn_from_error(
                        getattr(llm, "_provider_id", None), llm._model, _limit_err
                    )
                    if not _fenster:
                        raise
                    _final_messages = model_limits.fit_messages(
                        _final_messages,
                        model_limits.context_chars(_fenster, model_limits.CHAT_SHARE),
                    )
                    stream = await _open_stream(_final_messages)
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
                        # Arrow connectors are dropped here, before the token reaches the
                        # browser — the live stream is what the learner reads, so a later
                        # cleanup of the finished answer would come too late.
                        _tok = _strip_arrow_connectors(delta.content)
                        answer_parts.append(_tok)
                        yield f"data: {json.dumps({'token': _tok})}\n\n"
                        _line_buf += _tok
                        # Intra-line degeneration loop (no newline) — cut the runaway
                        # before it grows to 100k+ chars / minutes of streaming.
                        if len(_line_buf) - _last_intra >= _INTRA_LINE_CHECK_EVERY:
                            _last_intra = len(_line_buf)
                            if _tail_repeats(_line_buf):
                                logger.warning("Intra-line repetition loop detected, stopping stream")
                                _loop_detected = True
                                break
                        while "\n" in _line_buf:
                            _completed, _line_buf = _line_buf.split("\n", 1)
                            _last_intra = min(_last_intra, len(_line_buf))  # buffer shrank → re-baseline
                            if _prewarmer is not None:
                                _prewarmer.feed_line(_completed)
                            if _repeat_guard.is_loop(_completed):
                                logger.warning("Repetition loop detected, stopping stream")
                                _loop_detected = True
                                break
                    if _loop_detected:
                        break
            except Exception as e:
                _log_status = "error"
                logger.error("LLM stream error: {}", e)
                # War der Anbieter ueberlastet oder stumm, sagt das die Oberflaeche
                # als "spaeter noch einmal" statt als "Es ist ein Fehler aufgetreten".
                # Der rohe Text bleibt fuers Log dabei, der Schluessel steuert den Satz.
                _err = {"error": str(e)}
                _code = upstream_error_code(e)
                if _code:
                    _err["code"] = _code
                yield f"data: {json.dumps(_err)}\n\n"
                return
            finally:
                if stream is not None:
                    try:
                        await stream.close()
                    except Exception:
                        pass

            # Streaming finished: feed the trailing newline-less last line, then stop the pump
            # and await its final flush so the prewarm caches are complete + stable before the
            # attribution below reads them.
            if _prewarmer is not None and _pump_task is not None:
                if _line_buf.strip():
                    _prewarmer.feed_line(_line_buf)
                _pump_stop.set()
                try:
                    await _pump_task
                except Exception:
                    pass

            _clean_answer = _dedup_repeated_lines(_collapse_repeats(_sanitize_citations("".join(answer_parts).strip())))
            # Kill redundant structure the model adds on "zeige mir alle Quellen": a
            # one-row table that just echoes a sentence, and a textual "Quellen:" source
            # enumeration. The nav chips already list every source/page, so both are noise.
            # Deterministic (independent of the model obeying the prompt).
            _clean_answer = _strip_tiny_tables(_clean_answer)
            if source_ids:
                _clean_answer = _strip_source_list(_clean_answer, [q.get("filename", "") for q in source_qmap])
            # Unified post-hoc attribution for every RAG answer (specific / generic / scope):
            # the model wrote plain text; we embed each substantial line, pgvector-search the
            # active sources, cross-check the hit against the pages actually retrieved into
            # context, and attach a nav-only chip. Popup/direct answers (their own selected
            # text + AIA_SYSTEM_DIRECT prompt) get no RAG attribution.
            # Eine reine Absage ueberspringt den ganzen Durchgang: sie hat nichts zu belegen,
            # und der Weg darunter hat ihre einzige Zeile bisher erst eingebettet und
            # durchsucht, nur um sie danach als Absage wieder zu verwerfen. Genau diese
            # Zugabe war die Pause unter einer Antwort, die gar keinen Chip bekommen kann.
            # Woertlicher Vergleich, kein Aufruf nach draussen. Alles andere (andere Sprache,
            # zusammengesetzte Antwort) laeuft weiter ueber die Erkennung per Einbettung.
            if is_popup or not source_ids or is_sentinel_refusal(_clean_answer):
                answer = _clean_answer
            elif scope_single_page:
                # Single-page scope: skip per-line chips (they'd all repeat the named
                # page) and append ONE click-to-page anchor at the bottom — UNLESS the
                # answer is an honest "not in the sources" refusal. A refusal must never
                # carry a citation (the scoped page simply did not contain the answer), so
                # the anchor is suppressed via the same sentinel-proximity check the per-line
                # path uses. Embedding runs in a worker thread so the event loop stays free.
                _aqn = source_id_to_qnum.get(scope_chunks[0]["source_id"]) if scope_chunks else None
                _apg = next(iter(_scope_pages), None)
                if _aqn and _apg is not None:
                    from src.services.aia_embeddings import get_embedding_provider
                    from src.limits import AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS
                    _refused = await asyncio.to_thread(
                        is_refusal_answer, _clean_answer,
                        get_embedding_provider(
                            timeout=AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS,
                            retry_on_timeout=False).embed,
                        refusal_reference_texts())
                    answer = _clean_answer if _refused else _append_scope_anchor(_clean_answer, _aqn, _apg)
                else:
                    answer = _clean_answer
            else:
                from src.services.aia_embeddings import get_embedding_provider
                from src.limits import AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS
                # Der Nutzer liest den Text schon fertig und wartet nur noch auf die Chips.
                # Deshalb kurze Schranke und kein zweiter Versuch: kommt nichts, geht die
                # Antwort chiplos raus, statt sie an einer haengenden Gegenstelle festzuhalten.
                _prov = get_embedding_provider(timeout=AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS,
                                               retry_on_timeout=False)
                _stripped = _strip_inline_citation_chips(_clean_answer)  # defensive: model shouldn't emit chips now

                def _attribute_blocking() -> str:
                    # Batch-embed ALL candidate lines in ONE provider call (chunks into 100s
                    # internally) instead of one embed per line — same vectors, far fewer
                    # round-trips. search_one reuses the precomputed vector (per-line fallback).
                    # The canonical no-info SENTINELS ride along in the SAME batch (no extra
                    # round-trip): a candidate line embedding-near one of them is a refusal and
                    # is excluded from attribution, so a compound answer never sources its
                    # "not in the sources" sentence.
                    _cands = [ln for ln in _stripped.split("\n") if _needs_attribution(ln)]
                    # Sub-line queries ride in the SAME batch (no extra provider round-trips):
                    # a PROSE paragraph is attributed per sentence and a multi-fact line
                    # fact-by-fact, so each sentence/clause is searched on its own focused
                    # vector. Pre-embedding them here is load-bearing, NOT just an optimisation:
                    # the shared rate limit (2/s) cannot absorb one embed call per sentence.
                    _extra_units: list[str] = []
                    for _ln in _cands:
                        for _u in _attribution_subunits(_ln):
                            if _u not in _cands and _u not in _extra_units:
                                _extra_units.append(_u)
                    _batch_lines = _cands + _extra_units
                    _sentinels = refusal_reference_texts()
                    # Reuse whatever the streaming prewarm (B2) already embedded; embed only the
                    # misses plus the sentinels. If prewarm covered everything, this is just the
                    # sentinel embed and the after-answer pause is near zero.
                    _pw_vecs = _prewarmer.vecs if _prewarmer is not None else {}
                    _pw_hits = _prewarmer.hits if _prewarmer is not None else {}
                    _vec_by_line: dict[str, list] = {ln: _pw_vecs[ln] for ln in _batch_lines if ln in _pw_vecs}
                    _sentinel_vecs: list = []
                    _embed_s = 0.0
                    _embed_down = False
                    _n_prewarmed = len(_vec_by_line)
                    _miss_lines = [ln for ln in _batch_lines if ln not in _vec_by_line]
                    _to_embed = _miss_lines + _sentinels
                    if _to_embed:
                        try:
                            logger.info("post-hoc attribution: embedding {} lines ({} prewarmed of {}) + {} sentinels", len(_miss_lines), _n_prewarmed, len(_batch_lines), len(_sentinels))
                            _t_embed0 = time.perf_counter()
                            _vecs = _prov.embed(_to_embed)
                            _embed_s = time.perf_counter() - _t_embed0
                            if len(_vecs) == len(_to_embed):
                                for _ln, _v in zip(_miss_lines, _vecs[:len(_miss_lines)]):
                                    _vec_by_line[_ln] = _v
                                _sentinel_vecs = _vecs[len(_miss_lines):]
                        except Exception as e:
                            # Der eine Stapelaufruf ist gescheitert, also ist die Gegenstelle
                            # gerade nicht ansprechbar. Dann NICHT pro Zeile nachfassen: das
                            # waren frueher N weitere Aufrufe in dieselbe Schranke und der
                            # Hauptgrund, warum die Chips minutenlang ausblieben. Ohne Vektor
                            # gibt es keinen Chip, und das ist die richtige Zugabe-Absage.
                            _embed_down = True
                            logger.warning("post-hoc batch embedding failed, answer ships without chips: {}", e)
                    # Der Luecken-Satz wird WOERTLICH erkannt, nicht per Abstand: er und der
                    # Aussagesatz davor reden beide ueber die Quellen und liegen im
                    # Einbettungsraum zu dicht beieinander (gemessen 0,551 gegen 0,522, Schwelle
                    # 0,60). Ueber den Abstand verlöre der Aussagesatz seinen Chip mit.
                    _refusals = _refusal_lines(_cands, _vec_by_line, _sentinel_vecs)
                    _refusals |= {ln for ln in _cands if is_gap_line(ln)}
                    if _refusals:
                        logger.info("post-hoc attribution: {} refusal line(s) excluded from citation", len(_refusals))

                    def _raw_search(_line: str):
                        if _embed_down and _line not in _vec_by_line:
                            return []
                        try:
                            _qv = _vec_by_line.get(_line) or _prov.embed_one(_line)
                            # limit 10 (was 4): the attribution now FILTERS hits to pages
                            # actually retrieved, so it needs enough candidates to find the
                            # closest one the model saw (a fact often sits on several pages).
                            return db.hybrid_search_chunks(workspace["id"], _line, _qv,
                                                           source_ids=source_ids,
                                                           limit=10)
                        except Exception as e:
                            logger.warning("post-hoc attribution search failed for a line: {}", e)
                            return []

                    # Fan every per-line/-sentence DB search across a thread pool BEFORE the
                    # sequential attribution walk. These hit LOCAL pgvector (not the rate-limited
                    # embed API), so concurrency is free speed and was the ~13.7s bulk of the pause
                    # (measured ~3x faster this way). _batch_lines already mirrors exactly what
                    # _attribute_generic_text searches (candidate lines + their sentence/clause
                    # sub-units), so the walk turns into a dict lookup; a line not covered here
                    # falls back to one inline search. The chip (closest chunk by vec_distance) is
                    # identical to the serial path — only lower-ranked, non-chip hits reorder.
                    # Reuse prewarmed search hits; only search the lines the prewarm missed.
                    _t_search0 = time.perf_counter()
                    _hits_by_line: dict = {ln: _pw_hits[ln] for ln in _batch_lines if ln in _pw_hits}
                    _search_miss = [ln for ln in _batch_lines if ln not in _hits_by_line]
                    if _search_miss:
                        _hits_by_line.update(_parallel_search(_search_miss, _raw_search))
                    _search_s = time.perf_counter() - _t_search0

                    def _search_one(_line: str):
                        if _line in _hits_by_line:
                            return _hits_by_line[_line]
                        return _raw_search(_line)

                    # Looking a figure up beats ranking by meaning for exactly the claims a
                    # reader checks: the slide stating an office hour's time sat OUTSIDE the
                    # citation gate while three passages merely mentioning office hours took
                    # every slot. Cheap and cached per figure — a workspace-scoped ILIKE, and
                    # the same figure recurs across the lines of one answer.
                    _literal_cache: dict = {}

                    def _literal_lookup(_figure: str):
                        if _figure not in _literal_cache:
                            try:
                                _literal_cache[_figure] = db.find_chunks_containing(
                                    workspace["id"], _figure, source_ids=source_ids)
                            except Exception as e:
                                logger.warning("literal citation lookup failed for {}: {}", _figure, e)
                                _literal_cache[_figure] = []
                        return _literal_cache[_figure]

                    _attr_result = _attribute_generic_text(_stripped, _search_one, source_id_to_qnum,
                                                   # Chips may only point at pages the model
                                                   # actually saw (cross-check vs. retrieved pages).
                                                   seen_pages_by_source=seen_pages_by_source,
                                                   # GENERIC overview: drop the loose guarantee chip
                                                   # and chip-free the multi-law synthesis lines.
                                                   # Eine Umformung ist nie ein Ueberblick, auch wenn
                                                   # die Wegwahl fuer die Zeile GENERIC sagte.
                                                   overview=(intent == "GENERIC" and not scope_chunks
                                                             and not _umformen),
                                                   # Exact-match grounding sees exactly what the
                                                   # model read (the single neighbor-expanded window).
                                                   context_chunks=chunks,
                                                   # Who states this figure? Looked up, not ranked.
                                                   literal_lookup=_literal_lookup,
                                                   # Honest "not in the sources" lines get no chip,
                                                   # even inside an otherwise-grounded compound answer.
                                                   refusal_lines=_refusals,
                                                   # Explicit page/time scope ("ab Minute 40"): the
                                                   # post-hoc search still sweeps the WHOLE source, so
                                                   # clamp citations to the scoped chunks — otherwise a
                                                   # closer chunk from minute 13 leaks into the summary.
                                                   scope_chunks=scope_chunks,
                                                   # Dieselben Whisper-Segmente, die schon im Kontext
                                                   # stecken: der Medien-Chip zeigt damit auf das
                                                   # Segment mit dem zitierten Satz statt auf den
                                                   # Anfang des ganzen Chunks.
                                                   transcript_by_source=transcript_by_source)
                    _pw_flushes = _prewarmer.flushes if _prewarmer is not None else 0
                    logger.info(
                        "post-hoc attribution timing: embed {:.1f}s ({}/{} lines prewarmed in "
                        "{} stream-embed calls) + search {:.1f}s ({} searched inline) over {} "
                        "lines ({} candidates)",
                        _embed_s, _n_prewarmed, len(_batch_lines), _pw_flushes, _search_s,
                        len(_search_miss), len(_hits_by_line), len(_cands))
                    return _attr_result

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
            # B2: make sure the prewarm pump never outlives the stream. The success path
            # already stopped+awaited it before attribution; this cancels it on any early
            # exit (LLM error, client abort, CancelledError) so no background task leaks.
            if _pump_task is not None and not _pump_task.done():
                _pump_task.cancel()
            # Fallback: no save path ran (LLM error, CancelledError, yield exception
            # on a dead connection, anything else that bypassed the explicit
            # branches). Persist a marker either way - the user question was already
            # saved up-front, so skipping this leaves a question with nothing after
            # it after a reload, with no hint that anything went wrong. A stream that
            # produced text was cut off (aborted); one that died on an error without
            # any text is a failure the user can retry. Use a sync DB call so it
            # survives task cancellation - asyncio.to_thread would re-raise
            # CancelledError here.
            if not assistant_saved:
                partial = "".join(answer_parts).strip()
                _is_failure = _log_status == "error" and not partial
                try:
                    db.save_aia_message(
                        workspace["id"], user_id, "assistant", partial,
                        source_pages=source_pages, enrollment_id=enrollment_id,
                        source_qmap=source_qmap,
                        aborted=not _is_failure, failed=_is_failure,
                    )
                    if _log_status == "ok":
                        _log_status = "aborted"
                except Exception as e:
                    logger.warning("Fallback save of unfinished answer failed: {}", e)
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

