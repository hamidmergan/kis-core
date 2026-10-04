"""One question in, one streamed answer out, with sources and places attached at the end."""
import asyncio
import json
import re
import time
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from src.dependencies import get_current_user, get_llm_client
from src.features.campus import prompts
from src.features.campus.repository import chats as chat_repo
from src.features.campus.repository import chunks as chunk_repo
from src.features.campus.repository import places as place_repo
from src.features.campus.routes._title import make_title
from src.features.campus.services import retrieval
from src.features.campus.services.place_match import find_places
from src.i18n import get_locale, t
from src.limits import (
    CAMPUS_MAX_CHATS_PER_USER,
    CAMPUS_MAX_QUESTIONS_PER_CHAT,
    CAMPUS_QUESTION_MAX_CHARS,
    CAMPUS_SOURCE_CARDS_MAX,
)
from src.security.rate_limit import enforce_burst
from src.security.usage_log import log_request
from src.services import model_limits, provider_transport
from src.services.openai_compat_llm import OpenAICompatLLMClient
from src.services.upstream_errors import upstream_error_code

router = APIRouter(tags=["campus: chat"])

_LANG_RE = re.compile(r"^[A-Za-z][A-Za-z \-]{1,29}$")
_IDLE_SECONDS = 60.0


class ChatBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=CAMPUS_QUESTION_MAX_CHARS)
    chat_id: Optional[int] = None


def _understand(llm: OpenAICompatLLMClient, question: str, last_round: tuple[str, str] | None) -> tuple[str, str]:
    """Standalone search query and answer language; on any failure the question itself and no language."""
    try:
        resp = llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system", "content": prompts.precall_system()},
                {"role": "user", "content": prompts.precall_user(question, last_round)},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=model_limits.PRECALL_MAX_TOKENS,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        query = str(data.get("query") or "").strip() or question
        lang = str(data.get("lang") or "").strip()
        if not _LANG_RE.match(lang):
            lang = ""
        return query[:CAMPUS_QUESTION_MAX_CHARS], lang
    except Exception as e:  # noqa: BLE001
        logger.warning("Campus: Vor-Call fehlgeschlagen: {}", e)
        return question, ""


def _embed_one(text: str) -> list[float]:
    from src.services.aia_embeddings import get_embedding_provider_with_fallback
    return get_embedding_provider_with_fallback().embed_one(text)


def split_marker(text: str) -> tuple[bool, str]:
    """Whether the answer starts with the no-source marker, and the text without it."""
    stripped = text.lstrip()
    if stripped.startswith(prompts.NO_SOURCE_MARKER):
        return True, stripped[len(prompts.NO_SOURCE_MARKER):].lstrip()
    return False, text


@router.post("/chat")
async def campus_chat(
    body: ChatBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
    llm: OpenAICompatLLMClient = Depends(get_llm_client),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    enforce_burst(user_id, locale)
    provider_transport.exempt_this_request()
    question = body.question.strip()

    last_round = None
    if body.chat_id is not None:
        chat = chat_repo.get_chat(body.chat_id, user_id)
        if chat is None:
            raise HTTPException(status_code=404, detail=t("campus.chatNotFound", locale))
        if chat["question_count"] >= CAMPUS_MAX_QUESTIONS_PER_CHAT:
            raise HTTPException(status_code=409, detail={"message": t("campus.chatFull", locale), "kind": "chat_full"})
        chat_id = chat["id"]
        title = chat["title"]
        last_round = chat_repo.last_round(chat_id)
    else:
        title = make_title(question)
        chat_id = chat_repo.create_chat(user_id, title)
        chat_repo.enforce_chat_cap(user_id, CAMPUS_MAX_CHATS_PER_USER)

    query, answer_language = question, ""
    if last_round:
        query, answer_language = await asyncio.to_thread(_understand, llm, question, last_round)

    chat_repo.add_message(chat_id, "user", question)
    chat_repo.count_question(chat_id)

    context = await asyncio.to_thread(
        retrieval.build_context, query, _embed_one, chunk_repo.hybrid_search, chunk_repo.neighbors
    )
    messages = [
        {"role": "system", "content": prompts.answer_system(answer_language)},
        {"role": "user", "content": prompts.answer_user(context.text or "(no documents found)", question)},
    ]

    async def _stream() -> AsyncGenerator[str, None]:
        provider_transport.exempt_this_request()
        started = time.monotonic()
        status = "ok"
        tokens_in = tokens_out = None
        parts: list[str] = []
        held = ""
        marker_checked = False
        no_source = False
        try:
            yield f"data: {json.dumps({'meta': {'chat_id': chat_id, 'title': title}})}\n\n"
            stream = await llm._async_client.with_options(timeout=90.0, max_retries=0).chat.completions.create(
                model=llm._model,
                messages=messages,
                **llm.sampling(0.3),
                max_tokens=model_limits.CHAT_MAX_OUTPUT_TOKENS,
                stream=True,
                stream_options={"include_usage": True},
                **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
            )
            iterator = stream.__aiter__()
            while True:
                try:
                    chunk = await asyncio.wait_for(iterator.__anext__(), timeout=_IDLE_SECONDS)
                except StopAsyncIteration:
                    break
                if await request.is_disconnected():
                    status = "cancelled"
                    break
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    tokens_in = getattr(usage, "prompt_tokens", None)
                    tokens_out = getattr(usage, "completion_tokens", None)
                if not getattr(chunk, "choices", None):
                    continue
                piece = chunk.choices[0].delta.content or ""
                if not piece:
                    continue
                if not marker_checked:
                    # The first characters are held back only as long as they could still be the marker.
                    held += piece
                    probe = held.lstrip()
                    if len(probe) < len(prompts.NO_SOURCE_MARKER) and prompts.NO_SOURCE_MARKER.startswith(probe):
                        continue
                    marker_checked = True
                    no_source, held = split_marker(held)
                    piece, held = held, ""
                    if not piece:
                        continue
                parts.append(piece)
                yield f"data: {json.dumps({'token': piece})}\n\n"
            if not marker_checked and held:
                no_source, held = split_marker(held)
                if held:
                    parts.append(held)
                    yield f"data: {json.dumps({'token': held})}\n\n"
            answer = "".join(parts).strip()
            if status == "cancelled":
                if answer:
                    chat_repo.add_message(chat_id, "assistant", answer, sources=[], places=[], no_source=no_source)
                return
            if not answer:
                status = "error"
                yield f"data: {json.dumps({'error': t('job.upstreamBusy', locale), 'code': 'empty_answer'})}\n\n"
                return
            sources = [] if no_source else context.sources[:CAMPUS_SOURCE_CARDS_MAX]
            places = [] if no_source else find_places(answer, place_repo.all_places())
            message_id = chat_repo.add_message(chat_id, "assistant", answer, sources=sources, places=places, no_source=no_source)
            yield f"data: {json.dumps({'done': True, 'answer': answer, 'sources': sources, 'places': places, 'no_source': no_source, 'message_id': message_id})}\n\n"
        except Exception as e:  # noqa: BLE001
            status = "error"
            logger.exception("Campus: Antwort fehlgeschlagen")
            yield f"data: {json.dumps({'error': t('job.upstreamBusy', locale), 'code': upstream_error_code(e)})}\n\n"
        finally:
            log_request(
                user_id, endpoint="campus", provider=getattr(llm, "_provider", None), model=getattr(llm, "_model", None),
                tokens_in=tokens_in, tokens_out=tokens_out, duration_ms=int((time.monotonic() - started) * 1000), status=status,
            )

    return StreamingResponse(
        _stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
