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
from src.limits import AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS, AIA_EMBED_QUERY_MAX_CHARS
from src.services import model_limits
from src.services.aia_embeddings import get_embedding_provider
from src.security.rate_limit import enforce_burst
from src.security.usage_log import log_request as _log_usage
from src.features.ai_assistant.prompts.popup_prompts import (
    AIA_POPUP_ACTIONS,
    AIA_SYSTEM_DIRECT,
    AIA_SYSTEM_DIRECT_WITH_CONTEXT,
)
from src.features.ai_assistant.prompts.query_understanding_prompts import (
    aia_query_understanding_system,
)
from src.features.ai_assistant.prompts.rag_chat import (
    aia_system_rag,
    aia_rag_user_message,
)
from src.features.ai_assistant.prompts.refusal_prompts import (
    is_gap_line,
    is_sentinel_refusal,
    refusal_reference_texts,
)
from . import _followup
from ._json_stream import AntwortStrom
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

# Laengere Fragen sind fast immer themenbezogen, der Vor-Call entfaellt.
_INTENT_MAX_WORDS = 30

# GENERIC: eine breite Suche setzt die Startpunkte, die Auffuellung weiter unten
# sorgt fuer die Breite ueber alle Quellen.
_GENERIC_RETRIEVE_LIMIT = 32
# Notnagel: gleichmaessige Stichprobe je Quelle, wenn die Suche nichts findet
# (etwa ein Video ohne durchsuchbaren Text).
_GENERIC_FALLBACK_SAMPLE = 8

# Seitenbezug in der Frage ("fasse Seite 5 zusammen"): die Seite wird direkt geholt,
# nicht gesucht, denn die Zahl steht selten im Seitentext. Das Schluesselwort davor
# verhindert, dass "die 5 wichtigsten Punkte" greift.
_PAGE_REF_RE = re.compile(
    r"\b(?:S\.\s*|Seiten?\s*|pp?\.\s*|pages?\s*)"
    r"(\d{1,4})"
    # Bereichstrenner: Bindestriche und/oder bis/to, auch vertippt. Ein blosses
    # Leerzeichen ("12 14") zaehlt NICHT als Bereich.
    r"(?:\s*(?:[-–—]+\s*(?:bis|to)?|bis|to)\s*[-–—]*\s*(\d{1,4}))?",
    re.IGNORECASE,
)
_MAX_PAGE_SPAN = 50

# Nachbar-Erweiterung (SPECIFIC): wie viele Treffer als Ankerpunkte dienen. Eine
# Angabe steht oft NEBEN dem Treffer, etwa der Name neben der Ueberschrift "Autoren".
_NEIGHBOR_ANCHORS = 24
# Wie viele Stellen die globale Suche liefert, bevor Nachbarn dazukommen.
_GLOBAL_CANDIDATES = 120
# Harte Obergrenze fuer den SPECIFIC-Kontext, unabhaengig vom Admin-Budget.
# Gemessen am 16.08.2026: Budget 250k -> 320k liess den Messsatz von 8/9 auf 6/9
# fallen. Mehr Kontext war schlechter.
_SPECIFIC_MAX_CHARS = 60000
_NEIGHBOR_RADIUS = 3
# Zwei Anker naeher als so viele Stellen: die Luecke dazwischen wird gefuellt, damit
# eine Angabe ZWISCHEN beiden nicht durchfaellt.
_NEIGHBOR_BRIDGE = 4
# Deckel fuer gleichzeitige DB-Abfragen, unter der Poolgroesse (20), damit parallele
# Suchen den Pool nie leerraeumen. Gilt je Prozess.
_RETRIEVE_CONCURRENCY = 10
_retrieve_sem: Optional[asyncio.Semaphore] = None

# NENNT DIE FRAGE EINE QUELLE BEIM NAMEN, wird die vorgezogen. Sonst gewinnt eine
# Quelle, die das Werk nur ZITIERT. Erkannt am Titelkopf von Seite 1: ein langes
# Fragewort, das in GENAU EINER Quelle passt. Allerweltswoerter passen ueberall und
# zaehlen darum nicht.
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
    for tok in qtokens:
        hits = [sid for sid, words in hdr_words.items()
                if any(_title_word_match(tok, w) for w in words)]
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


# Absage fuer einen Seiten- oder Zeitbezug, den wir nicht bedienen koennen. BEWUSST
# anders formuliert als der Absage-Satz: der meldet eine echte inhaltliche Luecke,
# dieser hier nur, dass genau diese Einschraenkung nicht geht.
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
            # Erzwingt gueltiges JSON statt es nur zu erbitten, wie in den drei Aufrufen
            # des Zeitplans auch. Nimmt dem Prompt die Formatarbeit ab.
            response_format={"type": "json_object"},
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


def _full_context_if_fits(source_ids: Optional[list[int]], max_chars: int) -> Optional[list[dict]]:
    """Return ALL chunks of the active sources iff their total fits the budget.

    For an overview/summary question over source(s) small enough to fit the
    context window, sending the full content beats retrieving a sample: the LLM
    sees the whole document, nothing is missed, and we skip the strategy LLM call
    entirely. Short-circuits to None as soon as the running total exceeds the
    budget, so a 117-page doc bails cheaply and falls back to retrieval.
    """
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
    # Auffuellen: die Suche allein laesst das Budget halb leer und eine Quelle kann
    # mit einer einzigen Stelle dastehen. Der Rest wird reihum ueber alle Quellen
    # gefuellt, Treffer zuerst, dann jede Quelle abwechselnd.
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

    # _seq ist die Runde je Quelle. _order_round_robin verschraenkt danach: erst
    # Runde 0 aller Quellen, dann Runde 1. Schneidet das Budget ab, faellt hinten
    # weg, also behaelt jede Quelle ihre besten Stellen.
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


def _expand_with_neighbors(
    anchors: list[dict],
    doc_chunks: list[dict],
    radius: int,
    source_id: int,
    bridge: int = _NEIGHBOR_BRIDGE,
) -> list[dict]:
    """Weitet Anker zu Fenstern von ±``radius`` Stellen und schliesst Luecken.

    ``anchors`` sind die besten Treffer der Quelle, ``doc_chunks`` alle Stellen
    derselben Quelle in Dokumentreihenfolge. Jeder Anker wird zu ``[i-radius,
    i+radius]``; Fenster mit Abstand ``<= bridge`` verschmelzen, damit zwei Anker,
    die die Antwort EINRAHMEN, auch das Dazwischen mitnehmen. Zurueck kommen die
    abgedeckten Stellen in Dokumentreihenfolge, jede mit ``_anchor_dist``, dem
    Abstand zum NAECHSTEN Anker. Kleiner ist besser.

    Sortiert wird nach der fusionierten Note aus Vektor- und Stichwortsuche. Der
    reine Kosinus allein verwirft, was die Stichwortsuche gerade gefunden hat.

    Der Abstand gilt JE STELLE, nicht je Fenster. Frueher bekam jede Stelle eines
    verschmolzenen Fensters denselben Wert. Bei einem Transkript decken die Anker das
    ganze Dokument ab, alles wurde gleich bewertet, das Sortieren lief ins Leere und
    das Budget schnitt vorne ab: die Begruessung statt der Antwort.
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
        """Sort key and hop count of the anchor closest to chunk index ``j``.

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
        return (best[1], best[0]) if best else (1.0, 0)

    out: list[dict] = []
    for lo, hi in spans:
        for j in range(lo, hi + 1):
            c = dict(doc_chunks[j])
            c["source_id"] = source_id
            # ``_anchor_gap`` = Abstand zum Anker. Ohne ihn gewinnt beim Sortieren die
            # Stelle, die im Dokument frueher steht, und nicht die, die den Begriff
            # wirklich traegt.
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

    # NACHBAR-ERWEITERUNG. Die Suche liefert Ankerpunkte, dazu kommen die
    # Nachbarstellen im Dokument: die Antwort steht fast immer NEBEN etwas
    # Auffindbarem. Alles passt in EIN Fenster und wird in einem Aufruf beantwortet.
    #
    # Keine Fuzzy-Suche hier: die kostet ~3s je Aufruf und die Vektorsuche ist
    # gegen Tippfehler ohnehin robust.
    _sem = _get_retrieve_sem()

    # EINE Suche ueber ALLE Quellen, dann die besten Stellen zuerst, bis das Budget
    # voll ist. Frueher lief eine Suche je Quelle mit gestaffelter Platzverteilung,
    # weil die Noten je Quelle nicht vergleichbar waren. Seit die Stichwortsuche nach
    # Seltenheit gewichtet, ist die globale Suche gleich treffsicher (gemessen am
    # 16.08.2026 an 15 Faellen) und die Staffelung faellt weg.
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

    # Nachbarn holen. Das laeuft weiter JE QUELLE, weil ein Fenster nur innerhalb eines
    # Dokuments Sinn ergibt, aber es entscheidet nichts mehr ueber die Verteilung.
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

    # Nennt die Frage eine Quelle beim Titel, wird deren Note verbessert. Ein Dokument,
    # das sie nur ZITIERT, nimmt ihr so nicht mehr den Platz weg.
    if len(_je_quelle) > 1:
        _named = _named_source_ids(question, _headers)
        if _named:
            for c in alle:
                if c["source_id"] in _named:
                    c["_anchor_dist"] = c["_anchor_dist"] * _NAME_BOOST_FACTOR \
                        if c["_anchor_dist"] > 0 else c["_anchor_dist"] / _NAME_BOOST_FACTOR
            logger.info("SPECIFIC named-source boost → Quellen {}", sorted(_named))

    # Beste Stellen zuerst, bei gleicher Note der Anker vor seinen Nachbarn. Dann
    # auffuellen bis das Budget voll ist. Das ist die ganze Verteilung.
    alle.sort(key=lambda c: (c.get("_anchor_dist", 1.0), c.get("_anchor_gap", 0)))
    chunks = _take_chunks_within(alle, min(char_budget, _SPECIFIC_MAX_CHARS))
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
    """Pack chunks into ONE ``<documents>`` context string of ≤ ``budget`` chars.

    Every path (GENERIC / SPECIFIC / SCOPE / popup) is single-batch: a chunk that
    would overflow the budget is skipped, and later smaller chunks may still fit.
    Neighbor expansion bounds SPECIFIC to one coherent window too, so there is no
    map-reduce and no gap-filling hallucination.

    Returns ``(batches, seen_pages_by_source)`` where ``batches`` holds at most one
    entry and ``seen_pages_by_source`` are the pages the model saw (media sources
    map to an EMPTY set → the attribution cross-check reads that as "source
    retrieved, accept", since a timestamp chip has no page to validate). An empty
    ``chunks`` yields ``([], {})``.
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
    _ATTRIB_CANDIDATES,
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

    # Niveau-gerechte Antworten gibt es nur, wenn der Eigentuemer den Sprachtrainer
    # freigegeben UND der Leser ihn selbst eingeschaltet hat. Das Niveau haengt am
    # Nutzer, nicht am Workspace, darum braucht es beide Schalter.
    _adaptive_suffix, _applied_level = "", None
    if db.is_language_training_active(workspace["id"]) and _user_settings.get("language_training_active", False):
        # Beschreibung und Sprachprobe der Stufe kalibrieren den Ton. Ohne Niveau
        # aendert sich nichts. Haengt spaeter an der NUTZER-Nachricht direkt neben der
        # Frage, dort wiegt es beim Modell am schwersten.
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

    # VOR-CALL: ein LLM-Aufruf entscheidet GENERIC gegen SPECIFIC, holt einen
    # Seiten- oder Zeitbezug heraus und macht eine Folgefrage eigenstaendig
    # (siehe routes/_followup). Ist der Weg offensichtlich (Auswahl-Aktion, keine
    # Quellen, sehr lange Frage), entfaellt er und es gilt SPECIFIC ohne Bezug.
    # Der Verlauf erreicht NIE den Antwort-Aufruf, nur diesen Vor-Call.
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

    # Umformen der letzten Antwort ("in 3 Stichpunkten"): es gibt nichts zu suchen,
    # der Stoff IST diese Antwort. Suche und Kontext entfallen, die Chips der Runde
    # werden uebernommen.
    _umformen = _nachfrage == _followup.UMFORMEN and bool(_letzte_runde)
    if _umformen:
        logger.info("Chat: Folgefrage formt die letzte Antwort um ('{}'), keine Suche",
                    body.question[:60])
    elif _nachfrage == _followup.UMSCHREIBEN:
        logger.info("Chat: Folgefrage eigenstaendig gemacht: '{}' → '{}'",
                    body.question[:60], rewritten_question[:80])

    # Kontext-Budget in Zeichen, vom Admin einstellbar. Platz fuer die Frage wird
    # abgezogen: sie steht im Prompt NACH den Quellen, beides muss zusammen ins
    # Modellfenster passen.
    context_budget = _reserve_question_budget(_context_budget(), body.question)

    # ── Weg mit Seiten- oder Zeitbezug ──
    # "Seite 5" oder "Minute 10" wird aus GENAU diesen Stellen bedient, nicht gesucht.
    # Der Bezug kommt aus dem Vor-Call, _parse_page_refs ist der Notnagel ohne ihn.
    # Gilt fuer die ERSTE gewaehlte Quelle, sonst waere unklar, wessen Seite 5 gemeint ist.
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
                    # Ein Bereich ueber das halbe Dokument ist ein Ueberblick, kein
                    # Bezug. Also GENERIC statt Bezug, und ausdruecklich KEINE Absage.
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

    # Bezug verlangt, aber nicht bedienbar (falsche Quellenart, Seite gibt es nicht).
    # Statt zurueck in die Suche zu fallen und "steht nicht in den Quellen" zu
    # antworten, sofort die klare Absage. Kein LLM-Aufruf, keine Suche.
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

    # ABKUERZUNG: passen die gewaehlten Quellen ganz ins Budget, geht der volle Text
    # raus, ohne Suche und ohne Einbettung. Gemessen besser und schneller als eine
    # Stichprobe. Bei zu grossen Quellen bricht die Pruefung frueh ab.
    #
    # Auf welchen Quellen die Frage laeuft: bei einer Auswahl-Aktion genau dieses
    # Dokument, sonst die Anhaken-Auswahl. Die Quellenliste unter der Antwort
    # braucht das in JEDEM Zweig.
    search_source_ids = source_ids
    if body.source_uuid:
        popup_source = db.get_aia_source(body.source_uuid)
        if popup_source:
            search_source_ids = [popup_source["id"]]

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
        # ── GENERIC: eine breite Suche plus Auffuellen reihum ueber ALLE Quellen,
        # damit der Ueberblick jede Quelle beruehrt. Der Ueberblick-Prompt unten sorgt
        # dann fuer die Abdeckung Dokument fuer Dokument.
        provider = get_embedding_provider()
        chunks = await _retrieve_generic_context(
            provider, workspace["id"], source_ids, rewritten_question, budget=context_budget,
        )
    else:
        # ── Retrieval path: per-source hybrid + neighbor expansion (SPECIFIC) ──
        provider = get_embedding_provider()

        embed_text = body.source_text if body.source_text else rewritten_question
        # Zusammengesetzte Frage ("X und Y") wird je Teilsatz gesucht, sonst verdeckt
        # der staerkere Teil die Stellen zum schwaecheren und das Modell antwortet dazu
        # aus den falschen Seiten. Einfache Fragen behalten genau eine Suche.
        _retrieval_queries = (subqueries if (len(subqueries) > 1 and not body.source_text)
                              else [embed_text])

        chunks = await _retrieve_specific_context(
            provider, workspace["id"], search_source_ids,
            _retrieval_queries, rewritten_question, context_budget,
        )

    # Eine einzelne PDF-Seite: jede Zeile bekaeme denselben Chip auf die Seite, die
    # der Nutzer selbst genannt hat. Reines Rauschen, darum stattdessen EIN Anker
    # unten. Mehrere Seiten und Medien behalten ihre Chips je Zeile.
    _scope_pages = {c["page_number"] for c in (scope_chunks or []) if c.get("page_number") is not None}
    scope_single_page = bool(scope_chunks) and len(_scope_pages) == 1

    # Build source-number mapping (Q1, Q2, ...) for multi-source disambiguation
    all_sources_list = {s["id"]: s for s in db.get_aia_sources_by_workspace(workspace["id"])}
    source_id_to_qnum: dict[int, int] = {}
    source_qmap: list[dict] = []  # [{qnum, uuid, filename}, ...]
    # Q-Nummern in der Reihenfolge der Quellenliste in der Oberflaeche. Gleiche
    # Auswahl heisst gleiche Nummer bei jeder Anfrage.
    #
    # Nummeriert wird die AUSWAHL, nicht nur die Quellen mit Fundstelle: sonst stand
    # unter einer Antwort "11 Quellen", obwohl 13 angehakt waren, und es sah aus, als
    # haette der Leser zwei abgewaehlt. Quellen ohne Fundstelle bekommen eine Nummer,
    # die im Prompt nie auftaucht und auf die kein Beleg zeigt.
    chunk_sids = {c["source_id"] for c in chunks}
    qmap_sids = set(search_source_ids or []) | chunk_sids
    qnum_counter = 0
    for sid in all_sources_list:
        if sid not in qmap_sids:
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

    # Reihum sortieren: erst die N-te Stelle jeder Quelle, dann die N+1-te. Schneidet
    # das Budget ab, verliert jede Quelle nur hinten. SPECIFIC hat kein _seq.
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

    # Alle Stellen in EIN <documents>-Fenster packen. seen_pages_by_source sind die
    # Seiten, die das Modell wirklich gesehen hat: die Beleg-Pruefung laesst nur Chips
    # auf diese Seiten durch.
    batches, seen_pages_by_source = _pack_context_batches(
        chunks, context_budget, source_id_to_qnum, all_sources_list,
        transcript_by_source,
    )
    if _umformen:
        seen_pages_by_source = _umform_gesehen
    context = batches[0] if batches else "<documents>\n\n</documents>"
    _ctx_chars = sum(len(b) for b in batches)
    logger.info(
        "Context: {} batch(es), {} chars total (~{} tokens), budget {}/batch | {} chunks",
        len(batches), _ctx_chars, round(_ctx_chars / 3.5), context_budget, len(chunks),
    )

    # Build the LLM call. One context window → one call. No conversation history
    # is ever sent: each turn is fully standalone (no follow-up condensing, no leaks).
    messages: Optional[list[dict]] = None
    # Sprachanker: eine Frage ohne eigene Sprache ("hi", "klsdf") wuerde sonst auf
    # Englisch beantwortet und der Chat kippt mitten im Gespraech. Gelesen BEVOR
    # diese Runde gespeichert wird, es ist also wirklich die vorige Frage.
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
        # Nur "Erklaeren" braucht den Text drumherum. Uebersetzen und alles andere
        # arbeitet NUR auf der Auswahl, sonst geht die Anweisung im Kontext unter.
        # Erkannt am SCHLUESSEL, nicht an der Position in der Liste: die hat sich schon
        # einmal verschoben und die beiden Aktionen stillschweigend vertauscht.
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
    else:
        # OVERVIEW MODE only for a broad GENERIC ask (not a page/time SCOPE summary):
        # thematic lead-in + document-by-document coverage so all sources are touched.
        _overview = intent == "GENERIC" and not scope_chunks
        messages = [
            {"role": "system", "content": aia_system_rag(chat_lang, overview=_overview, prev_questions=_prev_questions)},
            {"role": "user", "content": aia_rag_user_message(context, rewritten_question, _prev_questions) + _adaptive_suffix},
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
        for chunk in chunks:
            source = all_sources_list.get(chunk["source_id"])
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
        try:
            # Send qmap upfront so the frontend can resolve [Q1], [Q2] chips
            # during streaming instead of falling back to activeSourceIds[0].
            yield f"data: {json.dumps({'qmap': source_qmap, 'source_pages': source_pages, 'applied_level': _applied_level})}\n\n"

            _final_messages = messages
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
            # Vorwaermen: waehrend die Antwort noch laeuft, werden fertige Zeilen schon
            # eingebettet und gesucht. Am Ende rechnet die Beleg-Zuordnung nur noch nach,
            # was fehlt.
            _do_prewarm = bool(source_ids) and not is_popup and not scope_single_page
            if _do_prewarm:
                # Kurze Schranke, kein zweiter Versuch: das Vorwaermen ist eine Abkuerzung.
                # Antwortet die Gegenstelle nicht, soll es das schnell merken und den Weg
                # freigeben, statt Threads an einer haengenden Anfrage zu binden.
                _pw_prov = get_embedding_provider(timeout=AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS,
                                   retry_on_timeout=False)

                def _pw_search(_ln, _vec):
                    try:
                        return db.hybrid_search_chunks(
                            workspace["id"], _ln, _vec or _pw_prov.embed_one(_ln),
                            source_ids=source_ids, limit=_ATTRIB_CANDIDATES,
                            # MUSS dieselbe Einschraenkung sein wie in _raw_search: der
                            # Cache liegt unter dem Zeilentext, zwei Kandidatenkreise
                            # unter demselben Schluessel waeren ein Zufallsergebnis.
                            seen_pages=seen_pages_by_source)
                    except Exception:
                        return []

                _prewarmer = _AttributionPrewarmer(_pw_prov.embed, _pw_search)
                _pump_stop = asyncio.Event()

                async def _prewarm_pump():
                    # Das Vorwaermen darf nur ein paar verteilte Aufrufe je Antwort kosten,
                    # nicht einen je Zeile. Der Rest laeuft am Ende in einem Aufruf mit.
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
            # Felder statt Fliesstext: die Form baut der Code, das Modell fuellt nur.
            _ANTWORT_SCHEMA = {
                "type": "json_schema",
                "json_schema": {
                    "name": "antwort", "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "gap": {"type": ["string", "null"]},
                            "bridge": {"type": ["string", "null"]},
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"term": {"type": "string"},
                                                   "text": {"type": "string"}},
                                    "required": ["term", "text"],
                                    "additionalProperties": False,
                                },
                            },
                            "body": {"type": "string"},
                        },
                        "required": ["gap", "bridge", "items", "body"],
                        "additionalProperties": False,
                    },
                },
            }
            _felder = not (body.source_text or _umformen)
            _strom_bau = AntwortStrom() if _felder else None

            async def _open_stream(messages):
                # 90s connect/first-token timeout so an Ollama cold-start model
                # load can finish before we abort. Once tokens flow the
                # inter-chunk inactivity guard below takes over.
                return await llm._async_client.with_options(timeout=90.0, max_retries=0).chat.completions.create(
                    model=llm._model,
                    messages=messages,
                    temperature=0.2,
                    stream=True,
                    **({"response_format": _ANTWORT_SCHEMA} if _felder else {}),
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
                # Sobald der Strom laeuft, greift die Zeitschranke der Bibliothek nicht
                # mehr. Wird die Gegenstelle stumm, warteten wir sonst ewig.
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
                        _roh_tok = (_strom_bau.feed(delta.content)
                                    if _strom_bau is not None else delta.content)
                        if not _roh_tok:
                            continue
                        # Arrow connectors are dropped here, before the token reaches the
                        # browser — the live stream is what the learner reads, so a later
                        # cleanup of the finished answer would come too late.
                        _tok = _strip_arrow_connectors(_roh_tok)
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
            # Doppelte Struktur entfernen, die das Modell bei "zeige mir alle Quellen"
            # anhaengt: eine Ein-Zeilen-Tabelle und eine Quellenliste im Text. Die Chips
            # zeigen das schon. Wird im Code erzwungen, nicht per Prompt erhofft.
            _clean_answer = _strip_tiny_tables(_clean_answer)
            # Der Satz aus dem eigenen Feld ist als Absage gesetzt, nicht geraten.
            _gap_satz = (_strom_bau.gap or "").strip() if _strom_bau is not None else ""
            if source_ids:
                _clean_answer = _strip_source_list(_clean_answer, [q.get("filename", "") for q in source_qmap])
            # BELEGE NACHTRAEGLICH: jede tragende Zeile wird eingebettet, in den aktiven
            # Quellen gesucht, gegen die tatsaechlich gelesenen Seiten geprueft und bekommt
            # einen Chip zum Hinspringen. Auswahl-Aktionen bekommen keine Belege.
            # Eine reine Absage ueberspringt den Durchgang: sie hat nichts zu belegen, und
            # das Einbetten ihrer einen Zeile war die Pause unter einer Antwort ohne Chip.
            if is_popup or not source_ids or is_sentinel_refusal(_clean_answer):
                answer = _clean_answer
            elif scope_single_page:
                # Einzelne Seite: statt Chips je Zeile EIN Anker unten. Ausser bei einer
                # Absage, die darf nie einen Beleg tragen.
                _aqn = source_id_to_qnum.get(scope_chunks[0]["source_id"]) if scope_chunks else None
                _apg = next(iter(_scope_pages), None)
                if _aqn and _apg is not None:
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
                # Der Nutzer liest den Text schon fertig und wartet nur noch auf die Chips.
                # Deshalb kurze Schranke und kein zweiter Versuch: kommt nichts, geht die
                # Antwort chiplos raus, statt sie an einer haengenden Gegenstelle festzuhalten.
                _prov = get_embedding_provider(timeout=AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS,
                                               retry_on_timeout=False)
                _stripped = _strip_inline_citation_chips(_clean_answer)  # defensive: model shouldn't emit chips now

                def _attribute_blocking() -> str:
                    # ALLE Zeilen in EINEM Aufruf einbetten statt einzeln. Die Muster-Absagen
                    # fahren im selben Stapel mit: eine Zeile, die einer davon nahe liegt, ist
                    # selbst eine Absage und bekommt keinen Beleg.
                    _cands = [ln for ln in _stripped.split("\n") if _needs_attribution(ln)]
                    # Auch die Teilstuecke fahren im selben Stapel: Fliesstext wird je Satz
                    # belegt, eine Zeile mit mehreren Angaben je Angabe. Das ist keine reine
                    # Beschleunigung, ein eigener Aufruf je Satz waere zu teuer.
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
                            # Stapelaufruf gescheitert heisst: die Gegenstelle ist gerade weg.
                            # Dann NICHT je Zeile nachfassen, das liess die Chips frueher
                            # minutenlang ausbleiben. Ohne Vektor eben kein Chip.
                            _embed_down = True
                            logger.warning("post-hoc batch embedding failed, answer ships without chips: {}", e)
                    # Der Absage-Satz wird WOERTLICH erkannt, nicht per Abstand: er und der
                    # Satz davor liegen zu dicht beieinander (0,551 gegen 0,522 bei Schwelle
                    # 0,60), sonst verlöre der Aussagesatz seinen Chip mit.
                    _refusals = _refusal_lines(_cands, _vec_by_line, _sentinel_vecs)
                    _refusals |= {ln for ln in _cands if is_gap_line(ln)}
                    if _gap_satz:
                        _refusals |= {ln for ln in _cands if _gap_satz in ln}
                    if _refusals:
                        logger.info("post-hoc attribution: {} refusal line(s) excluded from citation", len(_refusals))

                    def _raw_search(_line: str):
                        if _embed_down and _line not in _vec_by_line:
                            return []
                        try:
                            _qv = _vec_by_line.get(_line) or _prov.embed_one(_line)
                            # Die Einschraenkung auf gesehene Seiten steht in der ABFRAGE,
                            # nicht mehr nur als Filter dahinter. Vorher rankte die
                            # Datenbank den ganzen Workspace und _is_seen zerriss die
                            # Liste danach: ein passender Chunk hinter Platz 40 war schon
                            # weg, bevor der Filter ihn sah. Deshalb wurde das Limit
                            # zweimal hochgezogen (4 -> 10 -> 40), ein Pflaster.
                            return db.hybrid_search_chunks(workspace["id"], _line, _qv,
                                                           source_ids=source_ids,
                                                           limit=_ATTRIB_CANDIDATES,
                                                           seen_pages=seen_pages_by_source)
                        except Exception as e:
                            logger.warning("post-hoc attribution search failed for a line: {}", e)
                            return []

                    # Alle Zeilensuchen vorab parallel gegen die lokale Datenbank. Das war
                    # der Grossteil der Pause und ist so etwa 3x schneller. Der Durchgang
                    # darunter wird damit zum Nachschlagen. Bereits vorgewaermte Treffer
                    # werden wiederverwendet, gesucht wird nur, was fehlt.
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

                    # Eine Zahl nachschlagen schlaegt das Sortieren nach Bedeutung genau bei
                    # den Aussagen, die ein Leser nachprueft. Billig und je Zahl gemerkt.
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

            # Auswahl-Aktionen bekommen die Seite als Chip im Text, wie jede andere
            # Antwort. Ein Klick springt hin und markiert die Auswahl wieder.
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
            # Notfall: kein Speicherweg lief. Trotzdem etwas ablegen, sonst steht nach
            # dem Neuladen eine Frage ohne alles darunter. Mit Text heisst abgebrochen,
            # ohne Text heisst Fehler zum Wiederholen. Bewusst ein synchroner
            # Datenbankaufruf, damit er das Abbrechen der Aufgabe ueberlebt.
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
            # `or None` keeps the "no usage reported" case as None instead of a
            # misleading 0.
            _total_in = tokens_in or None
            _total_out = tokens_out or None
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

