"""AI assistant routes - chat + RAG."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale, t
from src.limits import AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS, FOLLOWUP_HISTORY_ROUNDS
from src.services import model_limits
from src.services.aia_embeddings import get_embedding_provider, get_embedding_provider_with_fallback
from src.security.rate_limit import enforce_burst
from src.security.usage_log import log_request as _log_usage
from src.features.ai_assistant.prompts.popup_prompts import (
    AIA_POPUP_ACTIONS,
    AIA_SYSTEM_DIRECT,
    AIA_SYSTEM_DIRECT_WITH_CONTEXT,
)
from src.features.ai_assistant.prompts.rag_chat import (
    aia_greeting_user_message,
    aia_system_greeting,
    aia_system_rag,
    aia_rag_user_message,
)
from src.features.ai_assistant.prompts.refusal_prompts import (
    is_only_gap,
    is_sentinel_refusal,
    refusal_reference_texts,
)
from . import _chat_failover
from . import _followup
from ._greeting import greeting_chunks, overview_chunks
from ._prewarm import start_prewarm
from ._source_map import build_source_pages, build_source_qmap, load_transcripts
from ._attribution_run import run_attribution
from ._retrieval import (
    _UEBERBLICK_INTENTS,
    _context_budget,
    _full_context_if_fits,
    _order_round_robin,
    _pack_context_batches,
    _reserve_question_budget,
    _retrieve_generic_context,
    _retrieve_specific_context,
)
from ._scope import _scope_unfulfillable_message, resolve_scope
from ._stream_helpers import _antwort_ohne_denken, _enrich_chat_trace, _stream_usage_tokens
from ._understand import _should_skip_intent_classification, _understand_query
from ._json_stream import _ANTWORT_SCHEMA, MAX_EINTRAEGE, AntwortStrom
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


from src.features.ai_assistant.routes._chips import _append_scope_anchor
from src.features.ai_assistant.routes._helpers import _trace_llm
from src.features.ai_assistant.routes._refusal import is_refusal_answer
from src.features.ai_assistant.routes._text import (
    _RepetitionGuard,
    _collapse_repeats,
    _dedup_repeated_lines,
    _sanitize_citations,
    _strip_arrow_connectors,
    _strip_inline_citation_chips,
    _strip_source_list,
    _strip_tiny_tables,
    _tail_repeats,
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
    from src.services import provider_transport
    _trace_llm(llm, "aia-chat")
    # A person waits for this answer live, so none of its calls waits for a provider seat.
    provider_transport.exempt_this_request()
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

    # Level-appropriate answers need the person's switch and a stored level.
    _adaptive_suffix, _applied_level = "", None
    if db.is_language_training_ready(user_id):
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
    _aeltere_runden: list[dict] = []
    if _should_skip_intent_classification(body.source_text, source_ids, body.question):
        intent, scope_raw, subqueries = "SPECIFIC", None, []
        _nachfrage, rewritten_question, _frage_sprache = _followup.KEINE, body.question, ""
        logger.info("Chat: pre-call skipped → SPECIFIC ('{}' across {} sources)",
                    body.question[:60], len(source_ids or []))
    else:
        import time as _t_pc
        _t_pc0 = _t_pc.monotonic()
        if _followup.lohnt_nachschlagen(body.question, body.source_text):
            _runden = await asyncio.to_thread(
                db.get_last_aia_rounds, workspace["id"], user_id, enrollment_id, FOLLOWUP_HISTORY_ROUNDS)
            _letzte_runde = _runden[-1] if _runden else None
            _aeltere_runden = _runden[:-1]
            if not _followup.ist_nachfrage_moeglich(
                    body.question, _letzte_runde, body.source_text):
                _letzte_runde = None
                _aeltere_runden = []
        intent, scope_raw, subqueries, _nachfrage, rewritten_question, _frage_sprache = await _understand_query(
            llm, body.question, _letzte_runde, _aeltere_runden)
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
    intent, scope_chunks, scope_requested = await asyncio.to_thread(
        resolve_scope,
        scope_raw, question=body.question, source_text=body.source_text,
        umformen=_umformen, source_ids=source_ids,
        resolved_sources=resolved_sources, intent=intent)

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

    # A greeting only names the topics, the summaries are enough for that.
    _gruss_chunks = (await asyncio.to_thread(greeting_chunks, source_ids, resolved_sources)
                     if _gruss else [])
    if _gruss_chunks:
        logger.info("Greeting: {} summaries stand in for the text, skipping retrieval",
                    len(_gruss_chunks))

    # An overview reads the summaries, they cover every source and are short.
    _ueberblick_chunks = (overview_chunks(source_ids, resolved_sources)
                          if intent == "GENERIC" and not (body.source_text or _umformen or scope_chunks)
                          else [])
    if _ueberblick_chunks:
        logger.info("Overview: {} summaries stand in for the text, skipping retrieval",
                    len(_ueberblick_chunks))

    _fit_full = (None if (body.source_text or _umformen or _gruss_chunks or _ueberblick_chunks
                          or intent not in _UEBERBLICK_INTENTS)
                 else await asyncio.to_thread(_full_context_if_fits, source_ids, context_budget))
    if _umformen:
        # No hits and no context, the material is the last answer itself.
        chunks = []
    elif scope_chunks:
        chunks = scope_chunks
    elif _gruss_chunks:
        chunks = _gruss_chunks
    elif _ueberblick_chunks:
        chunks = _ueberblick_chunks
    elif _fit_full is not None:
        chunks = _fit_full
        from collections import Counter
        _ps = Counter(c["source_id"] for c in chunks)
        logger.info("Fit-shortcut: {} chunks fit budget ({} chars), skipping retrieval | per-source: {}", len(chunks), context_budget, dict(_ps))
    elif intent in _UEBERBLICK_INTENTS:
        # Overview: one broad search plus round robin top-up across all sources.
        provider = get_embedding_provider_with_fallback()
        chunks = await _retrieve_generic_context(
            provider, workspace["id"], source_ids, rewritten_question, budget=context_budget,
        )
    else:
        # ── Retrieval path: per-source hybrid + neighbor expansion (SPECIFIC) ──
        provider = get_embedding_provider_with_fallback()

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
    source_id_to_qnum, source_qmap = build_source_qmap(
        all_sources_list, chunks, search_source_ids)

    # When reshaping, numbers and seen pages come from the old round.
    _umform_seiten: list[dict] = []
    if _umformen:
        _uuid_zu_id = {s["uuid"]: sid for sid, s in all_sources_list.items()}
        source_qmap, source_id_to_qnum, _umform_gesehen, _umform_seiten = _followup.letzte_quellen(
            _letzte_runde, _uuid_zu_id)

    # Sort round robin so every source only loses at the end when truncating.
    chunks = _order_round_robin(chunks, source_id_to_qnum)

    # Preload Whisper segments so timestamps make it into the media chunks.
    transcript_by_source = await asyncio.to_thread(load_transcripts, chunks, all_sources_list)

    # Pack all spots into one context window and record the pages seen.
    batches, seen_pages_by_source = _pack_context_batches(
        chunks, context_budget, source_id_to_qnum, all_sources_list,
        transcript_by_source,
    )
    if _umformen:
        seen_pages_by_source = _umform_gesehen
    elif _ueberblick_chunks:
        # A summary names no page, so the chips search every page of the chosen sources.
        seen_pages_by_source = None
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

    source_pages = build_source_pages(
        chunks, all_sources_list, umformen=_umformen,
        umform_pages=_umform_seiten, popup_entry=popup_entry)

    async def _stream() -> AsyncGenerator[str, None]:
        # The stream runs in its own task, the mark from the route has to be set there too.
        provider_transport.exempt_this_request()
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
                _prewarmer, _pump_task, _pump_stop = start_prewarm(
                    workspace_id=workspace["id"], source_ids=source_ids,
                    seen_pages_by_source=seen_pages_by_source)
            _felder = not (body.source_text or _umformen or _gruss)
            # The overview lives on breadth, only the single question gets a cap.
            _strom_bau = AntwortStrom(
                max_eintraege=None if _overview else MAX_EINTRAEGE,
            ) if _felder else None

            async def _open_stream(llm_client, messages):
                # Long timeout until the first character so a cold model can still load.
                return await llm_client._async_client.with_options(timeout=90.0, max_retries=0).chat.completions.create(
                    model=llm_client._model,
                    messages=messages,
                    # 0.7 instead of 0.2, too narrow a choice encourages repetition loops.
                    **llm_client.sampling(0.7),
                    # Without a ceiling a loop once ran up to 178,820 tokens.
                    max_tokens=model_limits.CHAT_MAX_OUTPUT_TOKENS,
                    stream=True,
                    **({"response_format": _ANTWORT_SCHEMA} if _felder else {}),
                    # Asks for a final chunk with the token counts for the log.
                    stream_options={"include_usage": True},
                    **(llm_client._extra_body and {"extra_body": llm_client._extra_body} or {}),
                )

            # The provider door in the client already falls back, the chain holds only the client itself.
            _chat_clients = _chat_failover.build_client_chain(llm)

            try:
                for _chain_idx, _llm in enumerate(_chat_clients):
                    _is_last_provider = _chain_idx == len(_chat_clients) - 1
                    try:
                        try:
                            stream = await _open_stream(_llm, _final_messages)
                        except Exception as _limit_err:  # noqa: BLE001
                            # If the refusal names the window size, it is shortened and sent again right away.
                            _fenster = model_limits.learn_from_error(
                                getattr(_llm, "_provider_id", None), _llm._model, _limit_err
                            )
                            if not _fenster:
                                raise
                            _final_messages = model_limits.fit_messages(
                                _final_messages,
                                model_limits.context_chars(_fenster, model_limits.CHAT_SHARE),
                            )
                            stream = await _open_stream(_llm, _final_messages)
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
                        break  # this provider served (or cleanly ended) the stream
                    except Exception as e:
                        if _chat_failover.should_failover(
                            e, has_output=bool(answer_parts), is_last_provider=_is_last_provider
                        ):
                            logger.warning(
                                "Chat-Anbieter {} gescheitert ({}), wechsle zu {}",
                                _llm._provider, e, _chat_clients[_chain_idx + 1]._provider,
                            )
                            continue
                        raise
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

                answer = await asyncio.to_thread(
                    run_attribution, _stripped,
                    prewarmer=_prewarmer, provider=_prov, workspace_id=workspace["id"],
                    source_ids=source_ids, seen_pages_by_source=seen_pages_by_source,
                    source_id_to_qnum=source_id_to_qnum, chunks=chunks,
                    transcript_by_source=transcript_by_source, scope_chunks=scope_chunks,
                    gap_sentence=_gap_satz, intent=intent, umformen=_umformen)

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

