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
)
from src.security.rate_limit import enforce_burst
from src.security.usage_log import log_request as _log_usage
from src.storage import USE_S3, delete_file, file_exists, get_file
from src.tool_prompts import (
    AIA_SYSTEM_DIRECT,
    AIA_SYSTEM_DIRECT_WITH_CONTEXT,
    aia_system_rag,
    aia_rag_user_message,
    AIA_QUERY_REWRITE,
    AIA_POPUP_ACTIONS,
    AIA_INTENT_CLASSIFIER_SYSTEM,
    AIA_INTENT_CLASSIFIER_FEWSHOT,
    AIA_SEARCH_STRATEGY_SYSTEM,
)

# Upper bound on the question length we hand to the LLM intent classifier.
# Longer questions are nearly always topic-specific (no need for an LLM round-trip)
# and very long inputs blow up the cheap-pre-filter premise of the classifier call.
_INTENT_MAX_WORDS = 30

# GENERIC (overview) retrieval: how many sub-queries the strategy LLM may emit,
# and how many chunks each sub-query pulls. Together they fan out across the
# document; the shared char budget at the call site truncates the merged result.
_GENERIC_MAX_QUERIES = 4
_GENERIC_PER_QUERY_LIMIT = 8

# Accept both ASCII [] and CJK lenticular 【】 - some LLMs emit the latter
# despite the prompt, and unstripped citations in history reinforce the
# wrong format on the next turn.
_CITATION_RE = re.compile(
    r"\s*[\[【](?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*\|[^\]】]+)?[\]】]"
)


# Smaller models sometimes emit `[N] S. X` or `[N] MM:SS` (closing the bracket
# before the position label). Repair to `[N, S. X]` / `[N, MM:SS]` so the
# frontend chip parser can render them as clickable citations.
_CITATION_FIX_TIME_RE = re.compile(r"\[(\d+)\]\s+(\d{1,2}:\d{2}(?::\d{2})?)")
_CITATION_FIX_PAGE_RE = re.compile(r"\[(\d+)\]\s+(S\.\s*\d+(?:[-,–]\s*\d+)*)")


def _sanitize_citations(text: str) -> str:
    """Repair malformed `[N] pos` citations into the chip-renderable `[N, pos]` form."""
    text = _CITATION_FIX_TIME_RE.sub(r"[\1, \2]", text)
    text = _CITATION_FIX_PAGE_RE.sub(r"[\1, \2]", text)
    return text


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


async def _rewrite_query(llm, history: list[dict], question: str) -> str:
    """Condense follow-up question to standalone using conversation history.

    Returns original question if rewrite fails, output is empty, or result is
    suspiciously long (defensive against LLM over-elaboration). Runs in a
    worker thread so a stalled provider cannot block the event loop.
    """
    import asyncio
    hist_text = "\n".join(
        f"{m['role']}: {_CITATION_RE.sub('', m['content'])}" for m in history
    )
    messages = [
        {"role": "system", "content": AIA_QUERY_REWRITE},
        {
            "role": "user",
            "content": f"History:\n{hist_text}\n\nLatest: {question}\nOutput:",
        },
    ]
    def _call():
        # 60s covers Ollama cold-start model load (see _classify_intent).
        return llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=messages,
            temperature=0.0,
            max_tokens=300,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
    try:
        response = await asyncio.to_thread(_call)
        rewritten = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("Query rewrite failed, using original: {}", e)
        return question
    if not rewritten or len(rewritten) > 1000:
        return question
    return rewritten


async def _generate_search_strategy(llm, question: str) -> list[str]:
    """Decompose a question into up to _GENERIC_MAX_QUERIES retrieval queries.

    The GENERIC (overview) path uses this so a broad question retrieves across
    the whole document instead of a single top-k slice (Open Notebook's "ask"
    strategy; addresses the known top-k-misses-spread-content limitation). One
    small LLM call, language-agnostic. Always includes the original question as a
    query and falls back to ``[question]`` on any error/empty output. Runs in a
    worker thread so a stalled provider cannot block the event loop.
    """
    import asyncio
    def _call():
        return llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system", "content": AIA_SEARCH_STRATEGY_SYSTEM},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=200,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
    try:
        response = await asyncio.to_thread(_call)
        msg = response.choices[0].message
        raw = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    except Exception as e:
        logger.warning("Search-strategy generation failed, using raw question: {}", e)
        return [question]
    terms: list[str] = []
    for line in raw.splitlines():
        t = re.sub(r"^\s*[-*\d.)\]]+\s*", "", line).strip().strip('"\'')
        if t and t.lower() not in (x.lower() for x in terms):
            terms.append(t)
    # Always keep the original question as an anchor query, dedup-aware.
    if question.strip().lower() not in (t.lower() for t in terms):
        terms.insert(0, question.strip())
    terms = terms[:_GENERIC_MAX_QUERIES]
    logger.info("Search strategy: {} queries for '{}'", len(terms), question[:60])
    return terms or [question]


async def _retrieve_generic_context(
    llm, provider, workspace_id: int, source_ids: list[int], question: str,
) -> list[dict]:
    """Build the GENERIC (overview) context purely from pgvector retrieval.

    Decomposes the question into a few sub-queries, runs each through hybrid
    search, merges + dedups the hits, then guarantees every active source is
    represented (per-source mini-search fallback, then the source's first chunk).
    No summaries involved — chunks + embeddings are the only precomputed data.
    """
    import asyncio
    terms = await _generate_search_strategy(llm, question)
    merged: list[dict] = []
    seen: set = set()
    question_vector = None
    for term in terms:
        vec = await asyncio.to_thread(provider.embed_one, term)
        if question_vector is None:
            question_vector = vec  # first query is the original question (anchor)
        hits = db.hybrid_search_chunks(
            workspace_id, term, vec, source_ids=source_ids,
            limit=_GENERIC_PER_QUERY_LIMIT,
        )
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
            chunks.extend(_sample(db.get_aia_chunks_by_source(sid), _GENERIC_PER_QUERY_LIMIT))
    logger.info("Generic retrieval: {} chunks across {} sources ({} queries)",
                len(chunks), len(source_ids or []), len(terms))
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
    (the caller backfills those via per-source search / doc-summary).
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
    _norm_for_match,
    _resolve_citation_pages,
    _strip_summary_citations,
    _chipify_inline_refs,
    _build_page_regions,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
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

    # Resolve active_source_ids (UUIDs → DB int ids)
    source_ids: list[int] | None = None
    if body.active_source_ids is not None:
        resolved = []
        for suuid in body.active_source_ids:
            source = db.get_aia_source(suuid)
            if source and source["workspace_id"] == workspace["id"]:
                resolved.append(source["id"])
        source_ids = resolved if resolved else None

    # Routing: GENERIC (cross-source overview, uses compact doc-summaries) vs
    # SPECIFIC (topic-focused, uses hybrid search). Cheap pre-filter avoids an
    # LLM round-trip when the answer is obvious (popup, no sources, long question).
    if _should_skip_intent_classification(body.source_text, source_ids, body.question):
        intent = "SPECIFIC"
    else:
        logger.info("Chat: calling intent classifier...")
        _t0 = _time.monotonic()
        intent = await _classify_intent(llm, body.question)
        logger.info("Chat: intent classifier returned after {:.1f}s", _time.monotonic() - _t0)
    logger.info("Chat intent: {} ('{}' across {} sources)", intent, body.question[:60], len(source_ids or []))

    # Default: question is used as-is. Only on the hybrid-search path with history
    # is it potentially rewritten (condense question).
    rewritten_question = body.question

    if intent == "GENERIC":
        # ── Overview path: pure pgvector multi-query retrieval (no summaries) ──
        from src.services.aia_embeddings import get_embedding_provider
        provider = get_embedding_provider()
        chunks = await _retrieve_generic_context(
            llm, provider, workspace["id"], source_ids, body.question,
        )
    else:
        # ── Normal path: hybrid search ──
        # Query rewriting (condense question): on a real follow-up, condense history into
        # a standalone question so the answer call stays history-free.
        # Skip for popup (source_text) and first question (no history).
        if not body.source_text:
            history_for_rewrite = db.get_aia_messages(
                workspace["id"], user_id, limit=4, enrollment_id=enrollment_id,
                include_aborted=False,
            )
            if history_for_rewrite:
                rewritten_question = await _rewrite_query(
                    llm, history_for_rewrite, body.question
                )
                if rewritten_question != body.question:
                    logger.info(
                        "Query rewritten: '{}' -> '{}'",
                        body.question[:80], rewritten_question[:80],
                    )

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

        chunks = db.hybrid_search_chunks(
            workspace["id"], embed_text, query_vector,
            source_ids=search_source_ids, limit=20,
        )
        found_pages = sorted(set(c["page_number"] for c in chunks))
        found_source_ids = sorted(set(c["source_id"] for c in chunks))
        logger.info("Hybrid Search: {} chunks, source_ids={}, Seiten: {}, Query: '{}'", len(chunks), found_source_ids, found_pages, embed_text[:80])

        # Source diversity: with multiple active sources at least 1 entry per source
        if source_ids and len(source_ids) > 1:
            diverse_chunks, remaining, missing = _diversify_by_source(chunks, source_ids)
            # Fallback for sources without a hybrid-search hit. A source can miss
            # the GLOBAL top-20 yet still be one the user wants compared, so we
            # first run a per-source mini-search to pull ITS OWN most-relevant
            # chunks (real pages/timestamps, citable). Only if that yields nothing
            # (e.g. a media source with no matchable text) do we fall back to the
            # compact doc-summary, then the first raw chunk.
            if missing:
                PER_SOURCE_FALLBACK_LIMIT = 3
                for sid in missing:
                    per_source = db.hybrid_search_chunks(
                        workspace["id"], embed_text, query_vector,
                        source_ids=[sid], limit=PER_SOURCE_FALLBACK_LIMIT,
                    )
                    if per_source:
                        diverse_chunks.extend(per_source)
                        logger.info("Source-Diversity fallback: source {} added via per-source search ({} chunks)", sid, len(per_source))
                        continue
                    # Last resort: the source's first raw chunk (no summaries exist
                    # in the pgvector-only design).
                    raw_fallback = db.get_aia_chunks_by_source(sid)
                    if raw_fallback:
                        diverse_chunks.append(raw_fallback[0])
                        logger.info("Source-Diversity fallback: source {} added via first chunk", sid)
            chunks = diverse_chunks + remaining

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

    # Build context (capped at AIA_CONTEXT_MAX_CHARS) - XML tags per chunk (Anthropic best practice).
    # source_index is built from the SAME chunks (only those that fit in context) so
    # the post-stream resolver can re-ground every citation's page/timestamp against
    # the real content the model actually saw. See _resolve_citation_pages.
    context_parts: list[str] = []
    context_len = 0
    source_index: dict[int, dict] = {}
    qnum_to_source_id: dict[int, int] = {}
    for chunk in chunks:
        qn = source_id_to_qnum.get(chunk["source_id"], 1)
        src = all_sources_list.get(chunk["source_id"])
        fname = src["filename"] if src else f"source-{qn}"
        if chunk.get("start_time") is not None:
            segments = transcript_by_source.get(chunk["source_id"], [])
            content = _enrich_media_content(chunk, segments) if segments else chunk["content"]
            loc = _format_timestamp(chunk["start_time"])
        else:
            content = chunk["content"]
            loc = f"S. {chunk['page_number']}"
        part = f'<document index="{qn}">\n<source>{fname} | {loc}</source>\n<content>\n{content}\n</content>\n</document>'
        if context_len + len(part) > AIA_CONTEXT_MAX_CHARS:
            break
        context_parts.append(part)
        context_len += len(part)
        is_media_chunk = chunk.get("start_time") is not None
        qnum_to_source_id[qn] = chunk["source_id"]
        si = source_index.setdefault(qn, {"is_media": False, "pages": set(), "chunks": []})
        si["chunks"].append({
            "page": None if is_media_chunk else chunk["page_number"],
            "start_time": chunk.get("start_time"),
            "norm_content": _norm_for_match(content),
        })
        if is_media_chunk:
            si["is_media"] = True
    context = f"<documents>\n{''.join(context_parts)}\n</documents>"

    # Validity set per PDF source = its REAL pages (chunks ∪ page-summaries), so the
    # citation resolver can reject pages no upstream step ever produced (e.g. a
    # hallucinated doc-summary [p.N]). Media sources keep an EMPTY page set on
    # purpose: a page number on a video/audio citation is always bogus -> dropped.
    for qn, si in source_index.items():
        if not si["is_media"]:
            si["pages"] = db.get_source_page_numbers(qnum_to_source_id[qn])
            # Per-page body vs header/footer split, so the resolver can de-weight
            # a term that only matched running page furniture (see _reroute_to_body).
            si["page_regions"] = _build_page_regions(
                db.get_aia_chunks_by_source(qnum_to_source_id[qn])
            )

    # Popup actions: user has selected text themselves
    if body.source_text:
        page_ref = f" [S. {body.source_page}]" if body.source_page else ""
        # "Elaborate" needs RAG context, the others work only with the selected text
        elaborate = AIA_POPUP_ACTIONS[0]
        elaborate_prefixes = (str(elaborate["prompt_de"]), str(elaborate["prompt_en"]))
        if body.question.startswith(elaborate_prefixes):
            system_prompt = AIA_SYSTEM_DIRECT_WITH_CONTEXT
            user_message = f"{body.question}\n\nMarkierter Text (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}\n\nWeiterer Kontext aus dem Dokument:\n{context}"
        else:
            system_prompt = AIA_SYSTEM_DIRECT
            user_message = f"{body.question}\n\nText (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}"
    else:
        system_prompt = aia_system_rag(chat_lang)
        user_message = aia_rag_user_message(context, rewritten_question)

    # Single-turn: system + user (no history in the answer call, to prevent leaks
    # from previous turns). History context was processed in the query
    # rewriter if needed and flowed into rewritten_question.
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
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
        try:
            # Send qmap upfront so the frontend can resolve [Q1], [Q2] chips
            # during streaming instead of falling back to activeSourceIds[0].
            yield f"data: {json.dumps({'qmap': source_qmap, 'source_pages': source_pages})}\n\n"
            aborted = False
            try:
                # 90s connect/first-token timeout so an Ollama cold-start model
                # load can finish before we abort. Once tokens flow the
                # inter-chunk inactivity guard below takes over.
                stream = await llm._async_client.with_options(timeout=90.0, max_retries=0).chat.completions.create(
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

            # First repair malformed `[N] S.X` -> `[N, S.X]`, then re-ground each
            # citation's page/timestamp against the real chunks via its keyword,
            # dropping any citation that can't be grounded (anti-hallucination).
            answer = _strip_summary_citations(
                _resolve_citation_pages(
                    _chipify_inline_refs(
                        _sanitize_citations("".join(answer_parts).strip()),
                        source_qmap,
                    ),
                    source_index,
                )
            )

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

            if is_popup:
                suffix = f" [S. {body.source_page}]"
                answer += suffix
                yield f"data: {json.dumps({'token': suffix})}\n\n"

            # Keywords in citations stay (used by frontend for highlighting)

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
            _log_usage(
                user_id=user_id,
                endpoint="chat",
                provider=getattr(llm, "_provider", None),
                model=getattr(llm, "_model", None),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_ms=int((_time.monotonic() - _started_at) * 1000),
                status=_log_status,
            )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

