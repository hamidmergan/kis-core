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
    KIA_SOURCE_MAX_PAGES,
    KIA_WORKSPACE_MAX_SOURCES,
    KIA_WORKSPACE_MAX_ACCESS_LINKS,
    KIA_NOTES_MAX_PER_USER,
)
from src.security.rate_limit import enforce_burst
from src.security.usage_log import log_request as _log_usage
from src.storage import USE_S3, delete_file, file_exists, get_file
from src.tool_prompts import (
    KIA_SYSTEM_DIRECT,
    KIA_SYSTEM_DIRECT_WITH_CONTEXT,
    kia_system_rag,
    KIA_QUERY_REWRITE,
    KIA_POPUP_ACTIONS,
)

# Accept both ASCII [] and CJK lenticular 【】 - some LLMs emit the latter
# despite the prompt, and unstripped citations in history reinforce the
# wrong format on the next turn.
_CITATION_RE = re.compile(
    r"\s*[\[【](?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*\|[^\]】]+)?[\]】]"
)


def _rewrite_query(llm, history: list[dict], question: str) -> str:
    """Condense follow-up question to standalone using conversation history.

    Returns original question if rewrite fails, output is empty, or result is
    suspiciously long (defensive against LLM over-elaboration).
    """
    hist_text = "\n".join(
        f"{m['role']}: {_CITATION_RE.sub('', m['content'])}" for m in history
    )
    messages = [
        {"role": "system", "content": KIA_QUERY_REWRITE},
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
@observe(name="kia-chat")
async def chat(
    workspace_uuid: str,
    body: schemas.ChatBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
    llm=Depends(get_llm_client),
    locale: str = Depends(get_locale),
):
    import time as _time
    _trace_llm(llm, "kia-chat")
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

    # Detection: generic summary request vs. specific question
    # Language-independent: short request + signal pattern = generic
    import re as _re
    _q_lower = body.question.strip().lower()
    _q_words = len(_q_lower.split())
    _GENERIC_SIGNALS = [
        r"fass\w*\b.*\bzusammen",
        r"zusammenfas+ung",
        r"überblick|übersicht",
        r"worum\s+geht\s+es",
        r"wovon\s+handelt",
        r"(kern|haupt)(aussagen|punkte|themen)",
        r"wichtigsten?\s+(punkte|aussagen|themen|inhalte)",
        r"(jede|alle)\w*\s+(source|datei|dokument)",
        # English
        r"summar(y|ize|ise)",
        r"overview",
        r"what.*(about|cover)",
        r"(main|key)\s+(points?|topics?|ideas?)",
        r"(each|every|all)\s+(source|file|document)",
    ]
    _has_signal = any(_re.search(p, _q_lower) for p in _GENERIC_SIGNALS)
    _is_generic = (
        not body.source_text
        and source_ids
        and _has_signal
        and _q_words <= 15  # short request = likely generic
    )

    # Default: question is used as-is. Only on the hybrid-search path with history
    # is it potentially rewritten (condense question).
    rewritten_question = body.question

    if _is_generic:
        # ── Generic summary: summaries + time-distributed media chunks ──
        logger.info("Generic summary detected for {} sources, skipping hybrid search", len(source_ids))
        all_sources_map = {s["id"]: s for s in db.get_aia_sources_by_workspace(workspace["id"])}
        chunks: list[dict] = []
        char_budget_per_source = 200000 // len(source_ids)

        for sid in source_ids:
            src = all_sources_map.get(sid)
            if not src:
                continue
            is_media = Path(src["filename"]).suffix.lower() in _MEDIA_EXTENSIONS

            if is_media:
                # Media: load all chunks sorted by time until budget is full
                all_media_chunks = db.get_aia_chunks_by_source(sid)
                all_media_chunks.sort(key=lambda c: c.get("start_time") or 0)
                taken: list[dict] = []
                total_chars = 0
                for c in all_media_chunks:
                    total_chars += len(c.get("content", ""))
                    if total_chars > char_budget_per_source:
                        break
                    taken.append(c)
                chunks.extend(taken)
                logger.info("Generic: source {} (media) → {} chunks from {} total", sid, len(taken), len(all_media_chunks))
            else:
                # PDF: use existing paragraph summaries (more compact than raw chunks)
                summaries = db.get_paragraph_summaries_by_source(sid)
                if summaries:
                    total_chars = 0
                    for s in summaries:
                        total_chars += len(s["summary"])
                        if total_chars > char_budget_per_source:
                            break
                        chunks.append({
                            "source_id": sid,
                            "page_number": s["page_number"],
                            "content": s["summary"],
                            "start_time": None,
                        })
                    logger.info("Generic: source {} (PDF) → {} summaries used", sid, min(len(summaries), len([c for c in chunks if c["source_id"] == sid])))
                else:
                    # Fallback: raw chunks distributed evenly across pages
                    all_pdf_chunks = db.get_aia_chunks_by_source(sid)
                    all_pdf_chunks.sort(key=lambda c: c.get("page_number") or 0)
                    sampled = []
                    total_chars = 0
                    if all_pdf_chunks:
                        step = max(1, len(all_pdf_chunks) // 10)
                        for i in range(0, len(all_pdf_chunks), step):
                            c = all_pdf_chunks[i]
                            total_chars += len(c.get("content", ""))
                            if total_chars > char_budget_per_source:
                                break
                            sampled.append(c)
                    chunks.extend(sampled)
                    logger.info("Generic: source {} (PDF, no summaries) → {} sampled chunks", sid, len(sampled))

        logger.info("Generic summary: {} total context chunks across {} sources", len(chunks), len(source_ids))
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

        # Source diversity: with multiple active sources at least 1 chunk per source
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
            # Fallback: include sources without hybrid-search hits anyway
            for sid in source_ids:
                if sid not in seen_sources:
                    fallback = db.get_aia_chunks_by_source(sid)
                    if fallback:
                        diverse_chunks.append(fallback[0])
                        seen_sources.add(sid)
                        logger.info("Source-Diversity fallback: source {} added with 1 chunk", sid)
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
        elaborate = KIA_POPUP_ACTIONS[0]
        elaborate_prefixes = (str(elaborate["prompt_de"]), str(elaborate["prompt_en"]))
        if body.question.startswith(elaborate_prefixes):
            system_prompt = KIA_SYSTEM_DIRECT_WITH_CONTEXT
            user_message = f"{body.question}\n\nMarkierter Text (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}\n\nWeiterer Kontext aus dem Dokument:\n{context}"
        else:
            system_prompt = KIA_SYSTEM_DIRECT
            user_message = f"{body.question}\n\nText (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}"
    else:
        system_prompt = kia_system_rag(chat_lang)
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

