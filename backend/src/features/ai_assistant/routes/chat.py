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
)
from src.security.rate_limit import enforce_burst
from src.security.usage_log import log_request as _log_usage
from src.storage import USE_S3, delete_file, file_exists, get_file
from src.tool_prompts import (
    AIA_SYSTEM_DIRECT,
    AIA_SYSTEM_DIRECT_WITH_CONTEXT,
    aia_system_rag,
    AIA_QUERY_REWRITE,
    AIA_POPUP_ACTIONS,
    AIA_INTENT_CLASSIFIER_SYSTEM,
    AIA_INTENT_CLASSIFIER_FEWSHOT,
)

# Upper bound on the question length we hand to the LLM intent classifier.
# Longer questions are nearly always topic-specific (no need for an LLM round-trip)
# and very long inputs blow up the cheap-pre-filter premise of the classifier call.
_INTENT_MAX_WORDS = 30

# Accept both ASCII [] and CJK lenticular 【】 - some LLMs emit the latter
# despite the prompt, and unstripped citations in history reinforce the
# wrong format on the next turn.
_CITATION_RE = re.compile(
    r"\s*[\[【](?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*\|[^\]】]+)?[\]】]"
)


# Inline position markers the doc-summary prompt asks the LLM to keep:
#   [p.5]       single page
#   [p.5-8]     page range
#   [p.3,7]     non-consecutive pages
#   [t:120]     media timestamp in seconds
#   [t:120-180] media range in seconds
_DOC_SUMMARY_MARKER_RE = re.compile(r"\[(p|t)\.?:?\s*([\d,\-\s]+)\]", re.IGNORECASE)


def _split_doc_summary_by_markers(summary: str) -> list[dict]:
    """Split a marker-annotated doc-summary into segments.

    Each segment becomes a virtual chunk with its own ``page_number`` (or
    ``start_time`` for media) so the chat LLM can build accurate citations. If
    the summary contains no markers (older summary or LLM ignored the format),
    returns a single segment with ``page_number=1`` so callers can still render
    a chip - just without precise position info.
    """
    matches = list(_DOC_SUMMARY_MARKER_RE.finditer(summary))
    if not matches:
        return [{"page_number": 1, "start_time": None, "content": summary.strip()}]

    segments: list[dict] = []
    for i, m in enumerate(matches):
        kind = m.group(1).lower()
        raw_value = m.group(2)
        # Use the first integer in the marker (e.g. "5-8" -> 5, "3,7" -> 3)
        first_int = re.search(r"\d+", raw_value)
        if not first_int:
            continue
        n = int(first_int.group())
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(summary)
        body = summary[body_start:body_end].strip().lstrip(":").strip()
        if not body:
            continue
        segments.append({
            "page_number": n if kind == "p" else 1,
            "start_time": float(n) if kind == "t" else None,
            "content": body,
        })
    return segments or [{"page_number": 1, "start_time": None, "content": summary.strip()}]


def _classify_intent(llm, question: str) -> str:
    """Decide GENERIC (cross-source overview) vs SPECIFIC (topic-focused) for routing.

    Single small LLM call - language-agnostic, replaces the old DE/EN regex list.
    On any error or unexpected output we fall back to SPECIFIC, the more
    conservative path (hybrid search still works for overview-ish questions,
    just costs more tokens).
    """
    raw = ""
    try:
        response = llm._client.chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system", "content": AIA_INTENT_CLASSIFIER_SYSTEM},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=200,  # leave headroom for reasoning preambles; we parse the verdict out
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
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


def _rewrite_query(llm, history: list[dict], question: str) -> str:
    """Condense follow-up question to standalone using conversation history.

    Returns original question if rewrite fails, output is empty, or result is
    suspiciously long (defensive against LLM over-elaboration).
    """
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
    try:
        response = llm._client.chat.completions.create(
            model=llm._model,
            messages=messages,
            temperature=0.0,
            max_tokens=300,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
        rewritten = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("Query rewrite failed, using original: {}", e)
        return question
    if not rewritten or len(rewritten) > 1000:
        return question
    return rewritten

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
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: chat"])

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
    _q_words = len(body.question.strip().split())
    if body.source_text or not source_ids or _q_words > _INTENT_MAX_WORDS:
        intent = "SPECIFIC"
    else:
        intent = _classify_intent(llm, body.question)
    logger.info("Chat intent: {} ('{}' across {} sources)", intent, body.question[:60], len(source_ids or []))

    # Default: question is used as-is. Only on the hybrid-search path with history
    # is it potentially rewritten (condense question).
    rewritten_question = body.question

    if intent == "GENERIC":
        all_sources_map = {s["id"]: s for s in db.get_aia_sources_by_workspace(workspace["id"])}
        chunks: list[dict] = []

        if len(source_ids) == 1:
            # ── Single source: use the richer page-summaries directly (covers
            # the full document, no compression artifact). Falls back to the
            # doc-summary for media/DOCX/PPTX or pre-rollout PDFs.
            sid = source_ids[0]
            src = all_sources_map.get(sid)
            page_sums = db.get_page_summaries_by_source(sid) if src else []
            if page_sums:
                for ps in page_sums:
                    chunks.append({
                        "source_id": sid,
                        "page_number": ps["page_number"],
                        "content": ps["summary"],
                        "start_time": None,
                    })
                logger.info("Generic single-source: used {} page-summaries", len(page_sums))
            elif src and (src.get("summary") or "").strip():
                chunks.append({
                    "source_id": sid,
                    "page_number": 1,
                    "content": src["summary"].strip(),
                    "start_time": None,
                })
                logger.info("Generic single-source: used doc-summary (no page-summaries)")
            else:
                fallback = db.get_aia_chunks_by_source(sid)
                if fallback:
                    chunks.append(fallback[0])
                logger.info("Generic single-source: used first-chunk fallback (no summaries yet)")
        else:
            # ── Multi-source overview ──
            # Each source contributes multiple anchored chunks so the LLM has
            # equal weight per source (otherwise media gets drowned out by PDFs):
            #   - PDFs: page-summaries (real page_number), capped to 12 evenly
            #     spaced pages.
            #   - Media: raw chunks (real start_time), capped to 8 evenly spaced.
            #   - Fallback: split doc-summary by inline markers, else first chunk.
            PAGE_SUMS_PER_SOURCE = 12
            MEDIA_CHUNKS_PER_SOURCE = 8

            def _sample(items: list, k: int) -> list:
                if len(items) <= k:
                    return items
                step = len(items) / k
                return [items[int(i * step)] for i in range(k)]

            for sid in source_ids:
                src = all_sources_map.get(sid)
                if not src:
                    continue
                page_sums = db.get_page_summaries_by_source(sid)
                if page_sums:
                    for ps in _sample(page_sums, PAGE_SUMS_PER_SOURCE):
                        chunks.append({
                            "source_id": sid,
                            "page_number": ps["page_number"],
                            "content": ps["summary"],
                            "start_time": None,
                        })
                    continue
                # Media (no page-summaries by design): sample raw chunks. Their
                # start_time gives clickable timestamps; multiple chunks give
                # the LLM enough anchor points to actually cite the video.
                raw_chunks = db.get_aia_chunks_by_source(sid)
                if raw_chunks and any(c.get("start_time") is not None for c in raw_chunks):
                    for c in _sample(raw_chunks, MEDIA_CHUNKS_PER_SOURCE):
                        chunks.append(c)
                    continue
                doc_summary = (src.get("summary") or "").strip()
                if doc_summary:
                    for seg in _split_doc_summary_by_markers(doc_summary):
                        chunks.append({
                            "source_id": sid,
                            "page_number": seg["page_number"],
                            "content": seg["content"],
                            "start_time": seg["start_time"],
                        })
                    continue
                fallback = db.get_aia_chunks_by_source(sid)
                if fallback:
                    chunks.append(fallback[0])

            logger.info("Generic multi-source: {} segments across {} sources", len(chunks), len(source_ids))
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
                rewritten_question = _rewrite_query(
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
        query_vector = provider.embed_one(embed_text)

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
            seen_sources: set[int] = set()
            diverse_chunks: list[dict] = []
            remaining: list[dict] = []
            for chunk in chunks:
                if chunk["source_id"] not in seen_sources:
                    seen_sources.add(chunk["source_id"])
                    diverse_chunks.append(chunk)
                else:
                    remaining.append(chunk)
            # Fallback for sources without a hybrid-search hit: prefer the compact
            # doc-summary (signals "this source covers X, Y, Z" without false-citation
            # risk) and fall back to the first raw chunk for sources still missing one.
            missing = [sid for sid in source_ids if sid not in seen_sources]
            if missing:
                all_sources_map = {s["id"]: s for s in db.get_aia_sources_by_workspace(workspace["id"])}
                for sid in missing:
                    src = all_sources_map.get(sid)
                    doc_summary = ((src or {}).get("summary") or "").strip()
                    if doc_summary:
                        # Use the first marker-segment as the fallback. The whole
                        # doc-summary is overkill for a "we missed this source"
                        # hint, and the first segment usually has the strongest
                        # topic signal anyway.
                        seg = _split_doc_summary_by_markers(doc_summary)[0]
                        diverse_chunks.append({
                            "source_id": sid,
                            "page_number": seg["page_number"],
                            "content": seg["content"],
                            "start_time": seg["start_time"],
                        })
                        seen_sources.add(sid)
                        logger.info("Source-Diversity fallback: source {} added via doc-summary", sid)
                    else:
                        raw_fallback = db.get_aia_chunks_by_source(sid)
                        if raw_fallback:
                            diverse_chunks.append(raw_fallback[0])
                            seen_sources.add(sid)
                            logger.info("Source-Diversity fallback: source {} added via first chunk (no doc-summary)", sid)
            chunks = diverse_chunks + remaining

    # Build source-number mapping (Q1, Q2, ...) for multi-source disambiguation
    all_sources_list = {s["id"]: s for s in db.get_aia_sources_by_workspace(workspace["id"])}
    source_id_to_qnum: dict[int, int] = {}
    source_qmap: list[dict] = []  # [{qnum, uuid, filename}, ...]
    qnum_counter = 0
    for chunk in chunks:
        sid = chunk["source_id"]
        if sid not in source_id_to_qnum:
            qnum_counter += 1
            source_id_to_qnum[sid] = qnum_counter
            src = all_sources_list.get(sid)
            if src:
                source_qmap.append({
                    "qnum": qnum_counter,
                    "uuid": src["uuid"],
                    "filename": src["filename"],
                    "is_media": Path(src["filename"]).suffix.lower() in _MEDIA_EXTENSIONS,
                })

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

    # Build context (max 200000 chars) - XML tags per chunk (Anthropic best practice)
    context_parts: list[str] = []
    context_len = 0
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
        if context_len + len(part) > 200000:
            break
        context_parts.append(part)
        context_len += len(part)
    context = f"<documents>\n{''.join(context_parts)}\n</documents>"

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
        user_message = f"{context}\n\nQuestion: {rewritten_question}"

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

    if is_popup:
        source_pages.append({
            "source_uuid": body.source_uuid,
            "filename": body.source_filename or "",
            "page_number": body.source_page,
            "source_text": body.source_text,
            "is_popup_selection": True,
        })
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
        try:
            # Send qmap upfront so the frontend can resolve [Q1], [Q2] chips
            # during streaming instead of falling back to activeSourceIds[0].
            yield f"data: {json.dumps({'qmap': source_qmap, 'source_pages': source_pages})}\n\n"
            answer_parts: list[str] = []
            aborted = False
            try:
                stream = await llm._async_client.chat.completions.create(
                    model=llm._model,
                    messages=messages,
                    temperature=0.2,
                    stream=True,
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

            answer = "".join(answer_parts).strip()

            if aborted:
                _log_status = "aborted"
                try:
                    langfuse_context.update_current_observation(
                        level="WARNING", status_message="client aborted stream"
                    )
                except Exception:
                    pass
                # Persist user question + partial answer flagged as aborted so
                # the rewriter can filter them out and the UI can render a marker.
                try:
                    await asyncio.to_thread(
                        db.save_aia_message,
                        workspace["id"], user_id, "user", body.question,
                        enrollment_id=enrollment_id,
                    )
                    await asyncio.to_thread(
                        db.save_aia_message,
                        workspace["id"], user_id, "assistant", answer,
                        source_pages=source_pages, enrollment_id=enrollment_id,
                        source_qmap=source_qmap, aborted=True,
                    )
                except Exception as e:
                    logger.warning("Failed to persist aborted chat message: {}", e)
                return

            if is_popup:
                suffix = f" [S. {body.source_page}]"
                answer += suffix
                yield f"data: {json.dumps({'token': suffix})}\n\n"

            # Keywords in citations stay (used by frontend for highlighting)

            # Save messages
            await asyncio.to_thread(
                db.save_aia_message,
                workspace["id"], user_id, "user", body.question,
                enrollment_id=enrollment_id,
            )
            await asyncio.to_thread(
                db.save_aia_message,
                workspace["id"], user_id, "assistant", answer,
                source_pages=source_pages, enrollment_id=enrollment_id,
                source_qmap=source_qmap,
            )

            # Send final metadata event - also send corrected answer
            yield f"data: {json.dumps({'done': True, 'answer': answer, 'source_pages': source_pages, 'source_qmap': source_qmap})}\n\n"
        finally:
            _log_usage(
                user_id=user_id,
                endpoint="chat",
                provider=getattr(llm, "_provider", None),
                model=getattr(llm, "_model", None),
                duration_ms=int((_time.monotonic() - _started_at) * 1000),
                status=_log_status,
            )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

