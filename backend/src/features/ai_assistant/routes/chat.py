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
    aia_greeting_user_message,
    aia_system_greeting,
    aia_system_rag,
    aia_rag_user_message,
)
from src.features.ai_assistant.prompts.refusal_prompts import (
    is_gap_line,
    is_only_gap,
    is_sentinel_refusal,
    refusal_reference_texts,
)
from . import _followup
from ._json_stream import MAX_EINTRAEGE, AntwortStrom
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

# Longer questions are almost always topical, the pre-call is skipped.
_INTENT_MAX_WORDS = 30

async def _antwort_ohne_denken(llm, messages: list[dict]) -> str:
    """Holt die Antwort ohne Strom und ohne Denken, jeden Schalter der Reihe nach."""
    import asyncio as _a

    from src.services import model_limits as _ml

    # Der schon aktive Schalter zuerst, danach die anderen. Nie zwei gleichzeitig,
    # das lehnen strenge Anbieter ab.
    _aktiv = getattr(getattr(llm, "_model_profile", None), "think_off", "") or ""
    _reihe = [_aktiv] if _aktiv else []
    _reihe += [n for n in _ml._SWITCH_ORDER if n != _aktiv]

    _grund = {k: v for k, v in (llm._extra_body or {}).items()
              if k not in _ml.THINK_OFF_SWITCHES}

    # Eigene Kopie, damit ein gelerntes Fenster hier auch wirkt.
    _msgs = list(messages)
    # Kleiner als im Strom, ein enges Fenster platzt sonst schon an der Ausgabe.
    _raum = min(_ml.CHAT_MAX_OUTPUT_TOKENS, 2048)

    def _hol(schalter: dict, nachrichten: list[dict]):
        antwort = llm._client.with_options(timeout=180.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=nachrichten,
            temperature=0.3,
            max_tokens=_raum,
            extra_body={**_grund, **schalter} or None,
        )
        nachricht = antwort.choices[0].message
        # Manche Denk-Modelle legen alles ins Denkfeld, dann ist das die Antwort.
        return (nachricht.content
                or getattr(nachricht, "reasoning_content", None)
                or getattr(nachricht, "reasoning", None)
                or "")

    for _name in _reihe:
        _schalter = dict(_ml.THINK_OFF_SWITCHES.get(_name) or {})
        if not _schalter:
            continue
        for _anlauf in (1, 2, 3, 4):
            try:
                _text = (await _a.to_thread(_hol, _schalter, _msgs)).strip()
            except Exception as e:  # noqa: BLE001 — abgelehnt heisst nur: naechster Anlauf
                _ml.learn_from_error(getattr(llm, "_provider_id", None), llm._model, e)
                # Relativ schrumpfen statt auf die Formel. Die rechnet mit 3 Zeichen
                # je Token, deutscher Text liegt naeher bei 2 und passt sonst nie.
                _zu_lang = "context length" in str(e).lower() or "max_tokens" in str(e).lower()
                _jetzt = sum(len(m.get("content") or "") for m in _msgs)
                if _zu_lang and _anlauf < 4 and _jetzt > _ml.MIN_CONTEXT_CHARS:
                    _msgs = _ml.fit_messages(
                        _msgs, max(_ml.MIN_CONTEXT_CHARS, int(_jetzt * 0.55))
                    )
                    logger.info("Nachschlag zu lang, gekuerzt auf {} Zeichen",
                                sum(len(m.get("content") or "") for m in _msgs))
                    continue
                logger.warning("Nachschlag mit Schalter {} fehlgeschlagen: {}",
                               _name, str(e)[:160])
                break
            if _text:
                logger.info("Nachschlag erfolgreich mit Schalter {}", _name)
                return _text
            break
    return ""


# Overview: a broad search sets the starting points, the top-up brings the breadth.
_GENERIC_RETRIEVE_LIMIT = 32
# Last resort: an even sample per source when the search finds nothing.
_GENERIC_FALLBACK_SAMPLE = 8

# A page reference in the question is fetched directly instead of searched.
_PAGE_REF_RE = re.compile(
    r"\b(?:S\.\s*|Seiten?\s*|pp?\.\s*|pages?\s*)"
    r"(\d{1,4})"
    # Range separators, a bare space does not count as a range.
    r"(?:\s*(?:[-–—]+\s*(?:bis|to)?|bis|to)\s*[-–—]*\s*(\d{1,4}))?",
    re.IGNORECASE,
)
_MAX_PAGE_SPAN = 50

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


def _parse_page_refs(question: str) -> list[int]:
    """Pulls explicit page numbers out of a question, sorted and without duplicates."""
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
    """Classifies the first chosen source as PDF, media or None."""
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
    """Reads the reference call's answer leniently, nonsense yields an empty reference."""
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
    """Expands page ranges into a sorted page list."""
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
    """Drops ranges that are almost certainly no real page or time reference."""
    if unit != "unknown":
        return intervals
    return [iv for iv in intervals if iv[1] is not None]


def _page_scope_too_large(intervals: list[list], max_page: Optional[int], limit: int) -> bool:
    """True when the page reference covers nearly the whole document and is thus an overview."""
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
    """Turns minute ranges into second windows, capped against absurd spans."""
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
    """Loads the chunks of the sources and keeps only the requested pages."""
    wanted = set(pages)
    chunks: list[dict] = []
    for sid in source_ids:
        chunks.extend(
            c for c in db.get_aia_chunks_by_source(sid) if c.get("page_number") in wanted
        )
    return chunks


def _retrieve_time_scoped_context(source_id: int, ranges_seconds: list[tuple]) -> list[dict]:
    """Loads a medium's chunks and keeps those that fall into the time window."""
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


# Refusal for a reference that cannot be served, worded differently from the content one.
_SCOPE_UNFULFILLABLE_MSG = {
    "de": "Dabei kann ich dir leider nicht weiterhelfen. Bitte formuliere deine Frage anders oder wähle das passende Material aus.",
    "en": "I'm afraid I can't help with that. Please rephrase your question or select the relevant source.",
}


def _scope_unfulfillable_message(scope_requested: bool, scope_chunks, chat_lang: str) -> Optional[str]:
    """Message for when a requested page or time reference could not be served."""
    if scope_requested and not scope_chunks:
        return _SCOPE_UNFULFILLABLE_MSG.get(chat_lang, _SCOPE_UNFULFILLABLE_MSG["de"])
    return None


def _parse_understanding(content: str) -> tuple[str, dict, list[str]]:
    """Reads route, reference and sub-questions from the pre-call answer."""
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
    _roh = str(obj.get("intent", "")).upper()
    intent = "GREETING" if "GREET" in _roh else ("GENERIC" if "GENERIC" in _roh else "SPECIFIC")
    scope_obj = obj.get("scope")
    scope = _parse_scope_response(json.dumps(scope_obj)) if scope_obj else {"unit": None, "intervals": []}
    subs_raw = obj.get("subqueries")
    subqueries = ([s.strip() for s in subs_raw if isinstance(s, str) and s.strip()][:3]
                  if isinstance(subs_raw, list) else [])
    return intent, scope, subqueries


# A language name and nothing more, the value goes unchecked into the next prompt.
_SPRACHNAME = re.compile(r"^[A-Za-z][A-Za-z \-]{1,29}$")


def _parse_answer_language(content: str) -> str:
    """The English name of the question language from the pre-call, empty when unusable."""
    import json
    raw = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    m = re.search(r"\{.*\}", raw.replace("```json", "").replace("```", ""), re.DOTALL)
    if not m:
        return ""
    try:
        name = str(json.loads(m.group(0)).get("lang", "")).strip()
    except Exception:
        return ""
    return name if _SPRACHNAME.match(name) else ""


async def _understand_query(
    llm, question: str, letzte_runde: Optional[dict] = None
) -> tuple[str, dict, list[str], str, str, str]:
    """One pre-call for everything: route, reference, sub-questions, follow-up and language."""
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
            # Forces valid JSON instead of merely asking for it.
            response_format={"type": "json_object"},
            # Room for sub-questions and for a model whose thinking cannot be turned off.
            max_tokens=model_limits.PRECALL_MAX_TOKENS,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
    try:
        response = await asyncio.to_thread(_call)
        msg = response.choices[0].message
        raw = msg.content or getattr(msg, "reasoning_content", None) or ""
    except Exception as e:
        logger.warning("Query understanding failed, defaulting to SPECIFIC/no-scope: {}", e)
        return "SPECIFIC", {"unit": None, "intervals": []}, [], _followup.KEINE, question, ""
    intent, scope, subqueries = _parse_understanding(raw)
    sprache = _parse_answer_language(raw)
    art, frage = (_followup.nachfrage_lesen(raw, question) if letzte_runde
                  else (_followup.KEINE, question))
    logger.info("Query understanding: '{}' → intent={} scope={} subqueries={} nachfrage={} sprache={} frage='{}'",
                question[:50], intent, scope, subqueries, art, sprache or "-", frage[:60])
    return intent, scope, subqueries, art, frage, sprache


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


def _should_skip_intent_classification(source_text, source_ids, question: str) -> bool:
    """Cheap pre-check that saves the routing call when the route is obvious."""
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
    """Pulls the token counts out of a stream chunk, otherwise (None, None)."""
    usage = getattr(chunk, "usage", None)
    if usage is None:
        return None, None
    return (
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


def _enrich_chat_trace(trace_id, question, answer, *, user_id, session_id) -> None:
    """Backfills question and answer via the trace id, errors stay silent."""
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
    # Caught here because the stream only runs after leaving this function.
    try:
        _trace_id = langfuse_context.get_current_trace_id()
    except Exception:
        _trace_id = None

    # Block on too many requests in a short time, raises 429.
    enforce_burst(user_id, locale)

    _started_at = _time.monotonic()
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    # The tutor language per course room and person drives the refusal sentence.
    _user_settings = db.get_aia_user_settings(workspace["id"], user_id) or {}
    chat_lang = _user_settings.get("chat_lang", "de")

    # Level-appropriate answers need both switches, course and person.
    _adaptive_suffix, _applied_level = "", None
    if db.is_language_training_active(workspace["id"]) and _user_settings.get("language_training_active", False):
        # The level block hangs on the user message, where it weighs most.
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

    # The source guard goes along with every chat and always stays last.
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

    # Resolve source UUIDs to database ids and keep the rows.
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

    # Pre-call: route, reference and follow-up in one go, the history stays here.
    _letzte_runde = None
    if _should_skip_intent_classification(body.source_text, source_ids, body.question):
        intent, scope_raw, subqueries = "SPECIFIC", None, []
        _nachfrage, rewritten_question, _frage_sprache = _followup.KEINE, body.question, ""
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
        intent, scope_raw, subqueries, _nachfrage, rewritten_question, _frage_sprache = await _understand_query(
            llm, body.question, _letzte_runde)
        logger.info("Chat: pre-call routed intent={} scope={} subqueries={} nachfrage={} in {:.1f}s ('{}' across {} sources)",
                    intent, scope_raw, len(subqueries), _nachfrage, _t_pc.monotonic() - _t_pc0, body.question[:60], len(source_ids or []))

    # When reshaping, the last answer is the material, search and context are skipped.
    _umformen = _nachfrage == _followup.UMFORMEN and bool(_letzte_runde)
    if _umformen:
        logger.info("Chat: Folgefrage formt die letzte Antwort um ('{}'), keine Suche",
                    body.question[:60])
    elif _nachfrage == _followup.UMSCHREIBEN:
        logger.info("Chat: Folgefrage eigenstaendig gemacht: '{}' → '{}'",
                    body.question[:60], rewritten_question[:80])

    # A bare greeting gets broad context and a prompt of its own.
    _gruss = intent == "GREETING" and not body.source_text and not _umformen
    if _gruss:
        logger.info("Chat: reiner Gruss ('{}'), eigener Weg ohne Absage", body.question[:40])

    # Context budget in characters, the room for the question is subtracted.
    context_budget = _reserve_question_budget(_context_budget(), body.question)

    # A page or time reference is served from exactly these spots, not searched.
    scope_chunks: Optional[list[dict]] = None
    scope_requested = False
    if not body.source_text and not _umformen:
        unit = scope_raw["unit"] if scope_raw else None
        intervals = scope_raw["intervals"] if scope_raw else []
        # An open range of bare numbers is a date, not a page reference.
        intervals = _servable_scope_intervals(unit, intervals)
        # Pattern-based last resort when the pre-call returned no reference.
        if not intervals:
            rx = _parse_page_refs(body.question)
            if rx:
                unit, intervals = "page", [[p, p] for p in rx]
        if intervals:
            kind = _first_source_kind(source_ids, resolved_sources)  # "pdf"|"media"|None
            # An explicit reference may refuse, bare numbers fall back into the search.
            explicit = unit in ("page", "time")
            scope_requested = explicit
            eff_unit = unit if explicit else (
                "page" if kind == "pdf" else "time" if kind == "media" else None)
            first_id = source_ids[0] if source_ids else None
            if first_id and eff_unit == "page" and kind == "pdf":
                max_page = max(db.get_source_page_numbers(first_id), default=None)
                if _page_scope_too_large(intervals, max_page, _MAX_PAGE_SPAN):
                    # A range over half the document is an overview, not a reference.
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

    # A requested but unservable reference refuses right away, without searching.
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

    # If the sources fit the budget entirely, the full text goes out without a search.
    search_source_ids = source_ids
    if body.source_uuid:
        popup_source = db.get_aia_source(body.source_uuid)
        if popup_source:
            search_source_ids = [popup_source["id"]]

    _fit_full = (None if (body.source_text or _umformen or intent not in _UEBERBLICK_INTENTS)
                 else _full_context_if_fits(source_ids, context_budget))
    if _umformen:
        # No hits and no context, the material is the last answer itself.
        chunks = []
    elif scope_chunks:
        chunks = scope_chunks
    elif _fit_full is not None:
        chunks = _fit_full
        from collections import Counter
        _ps = Counter(c["source_id"] for c in chunks)
        logger.info("Fit-shortcut: {} chunks fit budget ({} chars), skipping retrieval | per-source: {}", len(chunks), context_budget, dict(_ps))
    elif intent in _UEBERBLICK_INTENTS:
        # Overview: one broad search plus round robin top-up across all sources.
        provider = get_embedding_provider()
        chunks = await _retrieve_generic_context(
            provider, workspace["id"], source_ids, rewritten_question, budget=context_budget,
        )
    else:
        # ── Retrieval path: per-source hybrid + neighbor expansion (SPECIFIC) ──
        provider = get_embedding_provider()

        embed_text = body.source_text if body.source_text else rewritten_question
        # A compound question is searched per clause.
        _retrieval_queries = (subqueries if (len(subqueries) > 1 and not body.source_text)
                              else [embed_text])

        chunks = await _retrieve_specific_context(
            provider, workspace["id"], search_source_ids,
            _retrieval_queries, rewritten_question, context_budget,
        )

    # For a single PDF page one anchor sits at the bottom instead of a chip per line.
    _scope_pages = {c["page_number"] for c in (scope_chunks or []) if c.get("page_number") is not None}
    scope_single_page = bool(scope_chunks) and len(_scope_pages) == 1

    # Build source-number mapping (Q1, Q2, ...) for multi-source disambiguation
    all_sources_list = {s["id"]: s for s in db.get_aia_sources_by_workspace(workspace["id"])}
    source_id_to_qnum: dict[int, int] = {}
    source_qmap: list[dict] = []  # [{qnum, uuid, filename}, ...]
    # The whole selection is numbered, not only the sources with a hit.
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
    # An unexpected source gets a number too, otherwise its citation is lost.
    for chunk in chunks:
        sid = chunk["source_id"]
        if sid not in source_id_to_qnum:
            qnum_counter += 1
            source_id_to_qnum[sid] = qnum_counter

    # When reshaping, numbers and seen pages come from the old round.
    _umform_seiten: list[dict] = []
    if _umformen:
        _uuid_zu_id = {s["uuid"]: sid for sid, s in all_sources_list.items()}
        source_qmap, source_id_to_qnum, _umform_gesehen, _umform_seiten = _followup.letzte_quellen(
            _letzte_runde, _uuid_zu_id)

    # Sort round robin so every source only loses at the end when truncating.
    chunks = _order_round_robin(chunks, source_id_to_qnum)

    # Preload Whisper segments so timestamps make it into the media chunks.
    transcript_by_source: dict[int, list[dict]] = {}
    for chunk in chunks:
        sid = chunk["source_id"]
        if chunk.get("start_time") is not None and sid not in transcript_by_source:
            src = all_sources_list.get(sid)
            if src:
                transcript_by_source[sid] = _load_transcript_segments(src)

    # Pack all spots into one context window and record the pages seen.
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

    # One context window, one call, never a conversation history.
    messages: Optional[list[dict]] = None
    # Language anchor so a question without a language of its own cannot flip the chat.
    _prev_questions = [] if body.source_text else db.get_last_aia_user_questions(
        workspace["id"], user_id, enrollment_id=enrollment_id)
    if _umformen:
        # Reshaping gets its own prompt without a context window.
        messages = _followup.umform_nachrichten(
            _letzte_runde, rewritten_question, chat_lang, _prev_questions, _adaptive_suffix)
    elif body.source_text:
        # Popup actions: user has selected text themselves.
        page_ref = f" [S. {body.source_page}]" if body.source_page else ""
        # Only explain needs the surrounding text, recognised by the key instead of the position.
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
    elif _gruss:
        # Greeting: own prompt, no fields, the context only serves the topics.
        messages = [
            {"role": "system", "content": aia_system_greeting(chat_lang, _prev_questions)},
            {"role": "user",
             "content": aia_greeting_user_message(context, body.question) + _adaptive_suffix},
        ]
    else:
        # Overview mode only for a broad question, not for a reference.
        _overview = intent == "GENERIC" and not scope_chunks
        messages = [
            {"role": "system", "content": aia_system_rag(chat_lang, overview=_overview, prev_questions=_prev_questions,
                                             answer_language=_frage_sprache)},
            {"role": "user", "content": aia_rag_user_message(context, rewritten_question, _prev_questions, _frage_sprache) + _adaptive_suffix},
        ]

    # Build source_pages before streaming so we can send them at the end
    source_pages: list[dict] = []
    is_popup = bool(body.source_text and body.source_uuid and body.source_page)

    # Build the selection note early so it reappears on reload.
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

    # Save the question right away so it survives a cancelled stream.
    await asyncio.to_thread(
        db.save_aia_message,
        workspace["id"], user_id, "user", body.question,
        source_pages=[popup_entry] if popup_entry else None,
        enrollment_id=enrollment_id,
    )

    if _umformen:
        # The same spots as in the round being reshaped.
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
        # Status is set to error or cancelled, otherwise it stays ok.
        _log_status = "ok"
        stream = None
        answer_parts: list[str] = []
        assistant_saved = False
        # Declared here so the outer finally can always cancel the warm-up pump.
        _prewarmer = None
        _pump_task = None
        _pump_stop = None
        tokens_in: Optional[int] = None
        tokens_out: Optional[int] = None
        try:
            # The source numbers go out up front so chips resolve while streaming.
            yield f"data: {json.dumps({'qmap': source_qmap, 'source_pages': source_pages, 'applied_level': _applied_level})}\n\n"

            _final_messages = messages
            _line_buf = ""
            aborted = False
            # Guard against repetition loops, deduplication tidies up afterwards.
            _repeat_guard = _RepetitionGuard()
            _loop_detected = False
            # When there is nothing left in the stream, the reader discards every character.
            _nichts_mehr = False
            # The line guard only fires at the line end, so the buffer is checked as well.
            _last_intra = 0
            _INTRA_LINE_CHECK_EVERY = 1500
            # Warm-up: finished lines are embedded and searched while still streaming.
            _do_prewarm = bool(source_ids) and not is_popup and not scope_single_page
            if _do_prewarm:
                # Short timeout, no retry, the warm-up is only a shortcut.
                _pw_prov = get_embedding_provider(timeout=AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS,
                                   retry_on_timeout=False)

                def _pw_search(_ln, _vec):
                    try:
                        return db.hybrid_search_chunks(
                            workspace["id"], _ln, _vec or _pw_prov.embed_one(_ln),
                            source_ids=source_ids, limit=_ATTRIB_CANDIDATES,
                            # Must be the same restriction as in _raw_search, otherwise the cache does not match.
                            seen_pages=seen_pages_by_source)
                    except Exception:
                        return []

                _prewarmer = _AttributionPrewarmer(_pw_prov.embed, _pw_search)
                _pump_stop = asyncio.Event()

                async def _prewarm_pump():
                    # The warm-up may cost a few calls per answer, not one per line.
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
            # Fields instead of prose: the code builds the shape, the model only fills it.
            _ANTWORT_SCHEMA = {
                "type": "json_schema",
                "json_schema": {
                    "name": "antwort", "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            # The rule sits at the field, because that is where the model writes.
                            "no_info_sentence": {
                                "type": ["string", "null"],
                                "description": (
                                    "A whole sentence with subject and verb, saying what the "
                                    "documents do not state, with the asked-for term quoted "
                                    "inside it. Never a bare word or phrase. Always in the "
                                    "language of the question, never in the language of the "
                                    "examples. null when the documents do state what was asked."
                                ),
                            },
                            "bridge": {
                                "type": ["string", "null"],
                                "description": (
                                    "The second half of that same sentence, joined with a comma. "
                                    "Starts lowercase with a contrasting connector in the SAME "
                                    "language as no_info_sentence, names what the documents do "
                                    "describe instead, ends with a colon."
                                ),
                            },
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
                        "required": ["no_info_sentence", "bridge", "items", "body"],
                        "additionalProperties": False,
                    },
                },
            }
            _felder = not (body.source_text or _umformen or _gruss)
            # The overview lives on breadth, only the single question gets a cap.
            _strom_bau = AntwortStrom(
                max_eintraege=None if _overview else MAX_EINTRAEGE,
            ) if _felder else None

            async def _open_stream(messages):
                # Long timeout until the first character so a cold model can still load.
                return await llm._async_client.with_options(timeout=90.0, max_retries=0).chat.completions.create(
                    model=llm._model,
                    messages=messages,
                    # 0.7 instead of 0.2, too narrow a choice encourages repetition loops.
                    **llm.sampling(0.7),
                    # Without a ceiling a loop once ran up to 178,820 tokens.
                    max_tokens=model_limits.CHAT_MAX_OUTPUT_TOKENS,
                    stream=True,
                    **({"response_format": _ANTWORT_SCHEMA} if _felder else {}),
                    # Asks for a final chunk with the token counts for the log.
                    stream_options={"include_usage": True},
                    **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
                )

            try:
                try:
                    stream = await _open_stream(_final_messages)
                except Exception as _limit_err:  # noqa: BLE001
                    # If the refusal names the window size, it is shortened and sent again right away.
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
                # Once the stream runs, only this own silence timeout applies.
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
                        # Without cancelling, the model would keep writing invisibly.
                        if _strom_bau is not None and _strom_bau.genug:
                            logger.info("Eintragsgrenze erreicht, Strom beendet")
                            break
                        # After that none of the brakes below sees anything.
                        _nichts_mehr = _strom_bau is not None and _strom_bau.fertig
                        if not _roh_tok:
                            if _nichts_mehr:
                                logger.info("Strom beendet, {}", _strom_bau.grund)
                                break
                            continue
                        # Arrows drop out here already, the stream is what the learner reads.
                        _tok = _strip_arrow_connectors(_roh_tok)
                        answer_parts.append(_tok)
                        yield f"data: {json.dumps({'token': _tok})}\n\n"
                        _line_buf += _tok
                        # Cuts a loop without a line break before it gets out of hand.
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
                    if _nichts_mehr:
                        logger.info("Strom beendet, {}", _strom_bau.grund)
                        break
            except Exception as e:
                logger.error("LLM stream error: {}", e)
                # Ein Denk-Modell reisst den Strom mit, bevor ein Zeichen ankommt.
                # Vor der Fehlermeldung deshalb einmal ohne Denken nachfassen.
                _nachschlag = ""
                if not aborted and not "".join(answer_parts).strip():
                    _nachschlag = await _antwort_ohne_denken(llm, _final_messages)
                if _nachschlag:
                    logger.info("Strom gescheitert, Nachschlag ohne Denken lieferte {} Zeichen",
                                len(_nachschlag))
                    answer_parts.append(_nachschlag)
                    yield f"data: {json.dumps({'token': _nachschlag})}\n\n"
                else:
                    _log_status = "error"
                    # Overload is reported as 'try again later' instead of a raw error.
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

            # Netz gegen die leere Antwort: ein Denk-Modell verbraucht seine Ausgabe
            # im Denken und liefert nichts. Dann einmal ohne Denken nachfassen.
            if not aborted and not "".join(answer_parts).strip():
                _nachschlag = await _antwort_ohne_denken(llm, _final_messages)
                if _nachschlag:
                    logger.info("Leerer Strom, Nachschlag ohne Denken lieferte {} Zeichen",
                                len(_nachschlag))
                    answer_parts.append(_nachschlag)
                    yield f"data: {json.dumps({'token': _nachschlag})}\n\n"
                else:
                    # Lieber eine sichtbare Meldung als eine leere Blase.
                    _log_status = "error"
                    logger.error("Modell {} liefert auch ohne Denken nichts", llm._model)
                    yield f"data: {json.dumps({'error': t('job.upstreamBusy', locale), 'code': 'empty_answer'})}\n\n"
                    return

            # After the stream, deliver the last line and stop the pump cleanly.
            if _prewarmer is not None and _pump_task is not None:
                if _line_buf.strip():
                    _prewarmer.feed_line(_line_buf)
                _pump_stop.set()
                try:
                    await _pump_task
                except Exception:
                    pass

            _clean_answer = _dedup_repeated_lines(_collapse_repeats(_sanitize_citations("".join(answer_parts).strip())))
            # Removes the duplicate source list the model appends.
            _clean_answer = _strip_tiny_tables(_clean_answer)
            # The sentence from its own field is set as a refusal, not guessed.
            _gap_satz = (_strom_bau.gap or "").strip() if _strom_bau is not None else ""
            if source_ids:
                _clean_answer = _strip_source_list(_clean_answer, [q.get("filename", "") for q in source_qmap])
            # Back citations afterwards, refusals and greetings skip the pass.
            _nur_absage = (is_only_gap(_clean_answer, _gap_satz) if _gap_satz
                           else is_sentinel_refusal(_clean_answer))
            if is_popup or _gruss or not source_ids or _nur_absage:
                answer = _clean_answer
            elif scope_single_page:
                # For a single page one anchor at the bottom, except on a refusal.
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
                # Short timeout, if need be the answer goes out without chips.
                _prov = get_embedding_provider(timeout=AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS,
                                               retry_on_timeout=False)
                _stripped = _strip_inline_citation_chips(_clean_answer)  # defensive: model shouldn't emit chips now

                def _attribute_blocking() -> str:
                    # Embed all lines in one call, the model refusals ride along.
                    _cands = [ln for ln in _stripped.split("\n") if _needs_attribution(ln)]
                    # The sub-parts ride in the same batch too, one by one would be too expensive.
                    _extra_units: list[str] = []
                    for _ln in _cands:
                        for _u in _attribution_subunits(_ln):
                            if _u not in _cands and _u not in _extra_units:
                                _extra_units.append(_u)
                    _batch_lines = _cands + _extra_units
                    _sentinels = refusal_reference_texts()
                    # Reuses the warmed-up results and embeds only the missing ones.
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
                            # If the batch fails there is no per-line retry, then simply no chip.
                            _embed_down = True
                            logger.warning("post-hoc batch embedding failed, answer ships without chips: {}", e)
                    # The refusal sentence is matched verbatim, by distance it sits too close to a claim.
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
                            # The restriction to seen pages sits in the query, not as a filter behind it.
                            return db.hybrid_search_chunks(workspace["id"], _line, _qv,
                                                           source_ids=source_ids,
                                                           limit=_ATTRIB_CANDIDATES,
                                                           seen_pages=seen_pages_by_source)
                        except Exception as e:
                            logger.warning("post-hoc attribution search failed for a line: {}", e)
                            return []

                    # All line searches run in parallel up front, the pass below only looks them up.
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

                    # Looking up a number beats sorting by meaning.
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
                                                   # Chips may only point at pages the model really saw.
                                                   seen_pages_by_source=seen_pages_by_source,
                                                   # In the overview the loose chip is dropped, a reshaping is never an overview.
                                                   overview=(intent == "GENERIC" and not scope_chunks
                                                             and not _umformen),
                                                   # The verbatim match sees exactly what the model read.
                                                   context_chunks=chunks,
                                                   # Who states this figure? Looked up, not ranked.
                                                   literal_lookup=_literal_lookup,
                                                   # Refusal lines never get a chip.
                                                   refusal_lines=_refusals,
                                                   # An explicit reference brackets the citations to the named spots.
                                                   scope_chunks=scope_chunks,
                                                   # The same Whisper segments make the media chip point at the right segment.
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

            # Backfill question and answer onto the trace.
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
                # The half answer is stored as cancelled, the question was already there.
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

            # Selection actions get the page as a chip like any other answer.
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
            # Cancels the warm-up pump on every earlier exit.
            if _pump_task is not None and not _pump_task.done():
                _pump_task.cancel()
            # Emergency: store something anyway, otherwise a reload shows a question with nothing.
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
            # 'or None' keeps missing token counts as None instead of a misleading 0.
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

