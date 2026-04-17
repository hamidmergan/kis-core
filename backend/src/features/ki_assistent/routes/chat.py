"""KI-Assistent routes — chat + RAG."""

import io
import json
import re
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_kisski_client
from src.limits import (
    KIA_SOURCE_MAX_PAGES,
    KIA_MODULE_MAX_SOURCES,
    KIA_MODULE_MAX_ACCESS_LINKS,
    KIA_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
from src.tool_prompts import (
    KIA_SYSTEM_DIRECT,
    KIA_SYSTEM_DIRECT_WITH_CONTEXT,
    KIA_SYSTEM_RAG,
    KIA_POPUP_ACTIONS,
)

from src.features.ki_assistent.routes._helpers import (
    _trace_kisski,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_module,
    _save_source_file,
    _delete_source_files_for_module,
    _strip_image_text_layer,
    _markdown_fallback,
    _resolve_source_ids,
    _term_appears_in_text,
    _load_transcript_segments,
    _enrich_media_content,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ki_assistent import schemas

router = APIRouter(tags=["ki-assistent"])

@router.post("/ki-assistent/modules/{module_uuid}/chat")
@observe(name="kia-chat")
async def chat(
    module_uuid: str,
    body: schemas.ChatBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    _trace_kisski(kisski, "kia-chat")
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    # Sync module status: heal stale 'pending' if all sources are actually ready
    if module["status"] != "ready":
        sources_check = db.get_kia_sources_by_module(module["id"])
        ready_sources = [s for s in sources_check if s["status"] == "ready"]
        if not ready_sources:
            raise HTTPException(status_code=409, detail="Keine indizierten Quellen vorhanden")
        if all(s["status"] == "ready" for s in sources_check):
            db.update_kia_module_status(module_uuid, "ready")

    # Resolve active_source_ids (UUIDs → DB int ids)
    source_ids: list[int] | None = None
    if body.active_source_ids is not None:
        resolved = []
        for suuid in body.active_source_ids:
            source = db.get_kia_source(suuid)
            if source and source["module_id"] == module["id"]:
                resolved.append(source["id"])
        source_ids = resolved if resolved else None

    # Erkennung: generische Zusammenfassungs-Anfrage vs. spezifische Frage
    # Sprachunabhaengig: kurze Anfrage + Signal-Pattern = generisch
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
        r"(jede|alle)\w*\s+(quelle|datei|dokument)",
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
        and _q_words <= 15  # kurze Anfrage = wahrscheinlich generisch
    )

    if _is_generic:
        # ── Generische Zusammenfassung: Summaries + zeitlich verteilte Media-Chunks ──
        logger.info("Generic summary detected for {} sources, skipping hybrid search", len(source_ids))
        all_sources_map = {s["id"]: s for s in db.get_kia_sources_by_module(module["id"])}
        chunks: list[dict] = []
        char_budget_per_source = 200000 // len(source_ids)

        for sid in source_ids:
            src = all_sources_map.get(sid)
            if not src:
                continue
            is_media = Path(src["filename"]).suffix.lower() in _MEDIA_EXTENSIONS

            if is_media:
                # Media: alle Chunks zeitlich sortiert laden, bis Budget voll
                all_media_chunks = db.get_kia_chunks_by_source(sid)
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
                # PDF: vorhandene Paragraph-Summaries nutzen (kompakter als Raw-Chunks)
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
                    # Fallback: Raw-Chunks gleichmäßig über Seiten verteilt
                    all_pdf_chunks = db.get_kia_chunks_by_source(sid)
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
        # ── Normaler Pfad: Hybrid Search ──
        from src.services.kia_embeddings import get_embedding_provider
        provider = get_embedding_provider()

        embed_text = body.source_text if body.source_text else body.question
        query_vector = provider.embed_one(embed_text)

        # Bei Popup-Aktionen nur in der Quell-Datei suchen
        search_source_ids = source_ids
        if body.source_uuid:
            popup_source = db.get_kia_source(body.source_uuid)
            if popup_source:
                search_source_ids = [popup_source["id"]]

        chunks = db.hybrid_search_chunks(
            module["id"], embed_text, query_vector,
            source_ids=search_source_ids, limit=20,
        )
        found_pages = sorted(set(c["page_number"] for c in chunks))
        found_source_ids = sorted(set(c["source_id"] for c in chunks))
        logger.info("Hybrid Search: {} chunks, source_ids={}, Seiten: {}, Query: '{}'", len(chunks), found_source_ids, found_pages, embed_text[:80])

        # Source-Diversity: bei mehreren aktiven Quellen min. 1 Chunk pro Quelle
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
            # Fallback: Quellen ohne Hybrid-Search-Treffer trotzdem einbeziehen
            for sid in source_ids:
                if sid not in seen_sources:
                    fallback = db.get_kia_chunks_by_source(sid)
                    if fallback:
                        diverse_chunks.append(fallback[0])
                        seen_sources.add(sid)
                        logger.info("Source-Diversity fallback: source {} added with 1 chunk", sid)
            chunks = diverse_chunks + remaining

    # Build source-number mapping (Q1, Q2, ...) for multi-source disambiguation
    all_sources_list = {s["id"]: s for s in db.get_kia_sources_by_module(module["id"])}
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
    # (MM:SS) markers into each media chunk's context — lets the LLM cite
    # a precise timestamp within the chunk, not just the chunk start.
    transcript_by_source: dict[int, list[dict]] = {}
    for chunk in chunks:
        sid = chunk["source_id"]
        if chunk.get("start_time") is not None and sid not in transcript_by_source:
            src = all_sources_list.get(sid)
            if src:
                transcript_by_source[sid] = _load_transcript_segments(src)

    # Build context (max 200000 chars) — XML-Tags pro Chunk (Anthropic Best Practice)
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

    # Popup-Aktionen: User hat Text selbst markiert
    if body.source_text:
        page_ref = f" [S. {body.source_page}]" if body.source_page else ""
        # "Genauer ausführen" braucht RAG-Kontext, die anderen arbeiten nur mit dem markierten Text
        elaborate_prompt = KIA_POPUP_ACTIONS[0]["prompt"]
        if body.question.startswith(str(elaborate_prompt)):
            system_prompt = KIA_SYSTEM_DIRECT_WITH_CONTEXT
            user_message = f"{body.question}\n\nMarkierter Text (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}\n\nWeiterer Kontext aus dem Dokument:\n{context}"
        else:
            system_prompt = KIA_SYSTEM_DIRECT
            user_message = f"{body.question}\n\nText (aus {body.source_filename or 'Dokument'}{page_ref}):\n{body.source_text}"
    else:
        system_prompt = KIA_SYSTEM_RAG
        user_message = f"{context}\n\nQuestion: {body.question}"

    # Build multi-turn messages: system + history + current question
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Resolve enrollment_id for per-link chat separation
    enrollment_id = body.enrollment_id if not is_owner else None

    # Include recent chat history for follow-up questions (skip for popup actions)
    # Strip citation tags [Q1, S. 3] from history so the LLM doesn't re-cite old pages
    if not body.source_text:
        history = db.get_kia_messages(module["id"], user_id, limit=10, enrollment_id=enrollment_id)
        citation_re = re.compile(r"\s*\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*\|[^\]]+)?\]")
        for msg in history:
            messages.append({"role": msg["role"], "content": citation_re.sub("", msg["content"])})

    messages.append({"role": "user", "content": user_message})

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
        all_sources = {s["id"]: s for s in db.get_kia_sources_by_module(module["id"])}
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

    def _stream() -> Generator[str, None, None]:
        answer_parts: list[str] = []
        try:
            stream = kisski._client.chat.completions.create(
                model=kisski._model,
                messages=messages,
                temperature=0.2,
                stream=True,
                **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
            )
            for chunk_resp in stream:
                delta = chunk_resp.choices[0].delta if chunk_resp.choices else None
                if delta and delta.content:
                    answer_parts.append(delta.content)
                    yield f"data: {json.dumps({'token': delta.content})}\n\n"
        except Exception as e:
            logger.error("LLM stream error: {}", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        answer = "".join(answer_parts).strip()
        if is_popup:
            suffix = f" [S. {body.source_page}]"
            answer += suffix
            yield f"data: {json.dumps({'token': suffix})}\n\n"

        # Keywords in citations stay (used by frontend for highlighting)

        # Save messages
        db.save_kia_message(module["id"], user_id, "user", body.question, enrollment_id=enrollment_id)
        db.save_kia_message(module["id"], user_id, "assistant", answer, source_pages=source_pages, enrollment_id=enrollment_id, source_qmap=source_qmap)

        # Send final metadata event — also send corrected answer
        yield f"data: {json.dumps({'done': True, 'answer': answer, 'source_pages': source_pages, 'source_qmap': source_qmap})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

