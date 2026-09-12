"""The interpreter: single sentences, speech windows and the conversations kept at the account."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from pydantic import BaseModel, Field

from src.dependencies import get_current_user, get_translate_client_for_provider
from src.dependencies_rbac import require_tool_access
from src.features.interpreter import repository as repo
from src.features.interpreter import service
from src.i18n import TRANSLATE_LANGUAGES, get_locale, t
from src.security.rate_limit import enforce_tool_burst
from src.services.translation import TranslationService
from src.utils.file_validation import sanitize_pasted_text

router = APIRouter(
    tags=["interpreter"],
    dependencies=[Depends(require_tool_access("interpreter"))],
)

# A spoken sentence, not a document.
MAX_CHARS = 2000
Side = Literal["left", "right"]


class Sentence(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    target_lang: str
    provider_id: int | None = None
    glossary: dict[str, str] | None = None


class SessionIn(BaseModel):
    left_lang: str = "DE"
    right_lang: str = "EN-US"
    left_name: str = Field(default="", max_length=80)
    right_name: str = Field(default="", max_length=80)


class SessionPatch(BaseModel):
    left_lang: str | None = None
    right_lang: str | None = None
    left_name: str | None = Field(default=None, max_length=80)
    right_name: str | None = Field(default=None, max_length=80)
    ended: bool | None = None


class TurnIn(BaseModel):
    side: Side
    source: Literal["spoken", "typed"] = "spoken"
    original: str = Field(max_length=4000)
    translation: str = Field(default="", max_length=4000)
    status: Literal["translating", "done", "failed"] = "done"
    edited: bool = False
    at: int


def translate_text(body: Sentence, locale: str) -> str:
    """One sentence straight through the provider, no job."""
    if body.target_lang not in TRANSLATE_LANGUAGES:
        raise HTTPException(status_code=400, detail=t("interpreter.badTarget", locale))
    text = sanitize_pasted_text(body.text)
    if not text:
        raise HTTPException(status_code=400, detail=t("translate.textEmpty", locale))
    client, glossary = get_translate_client_for_provider(body.provider_id, glossary_entries=body.glossary or None)
    if client is None:
        raise HTTPException(status_code=503, detail=t("interpreter.noProvider", locale))
    return TranslationService(deepl_client=client, glossary=glossary), text


async def run_translation(body: Sentence, locale: str) -> dict:
    translation_service, text = translate_text(body, locale)
    try:
        # The provider call blocks, so it runs beside the event loop.
        translated = await run_in_threadpool(translation_service.translate_text, text, "", body.target_lang)
    except Exception as e:
        logger.warning("Interpreter translation failed: {}", e)
        raise HTTPException(status_code=502, detail=t("interpreter.failed", locale)) from e
    return {"text": translated, "target_lang": body.target_lang}


@router.post("/interpreter/translate")
async def translate_sentence(
    body: Sentence,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    enforce_tool_burst(current_user.get("user_id", 0), "interpreter", locale)
    return await run_translation(body, locale)


# Whisper takes a two-letter language code, anything else is ignored rather than passed on.
_LANGUAGE = re.compile(r"^[a-z]{2}$")


@router.post("/interpreter/transcribe")
async def transcribe_window(
    audio: UploadFile = File(...),
    provider_id: int | None = Form(None),
    language: str | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    enforce_tool_burst(current_user.get("user_id", 0), "interpreter", locale)
    lang = language.strip().lower() if language else None
    if lang and not _LANGUAGE.match(lang):
        lang = None
    return {"text": await service.transcribe_upload(audio, provider_id, lang, locale)}


def _own(session_id: str, current_user: dict, locale: str) -> dict:
    session = repo.get_session(session_id)
    if session is None or session["owner_id"] != current_user.get("user_id"):
        raise HTTPException(status_code=404, detail=t("interpreter.sessionUnknown", locale))
    return session


@router.post("/interpreter/sessions")
def create_session(
    body: SessionIn,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    for lang in (body.left_lang, body.right_lang):
        if lang not in TRANSLATE_LANGUAGES:
            raise HTTPException(status_code=400, detail=t("interpreter.badTarget", locale))
    session = repo.create_session(
        current_user.get("user_id", 0), body.left_lang, body.right_lang, body.left_name, body.right_name,
    )
    return service.state(session)


@router.get("/interpreter/sessions")
def list_sessions(current_user: dict = Depends(get_current_user)):
    return {"sessions": [service.summary(row) for row in repo.list_sessions(current_user.get("user_id", 0))]}


@router.get("/interpreter/sessions/{session_id}")
def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    return service.state(_own(session_id, current_user, locale))


@router.patch("/interpreter/sessions/{session_id}")
def patch_session(
    session_id: str,
    body: SessionPatch,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    session = _own(session_id, current_user, locale)
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items() if k != "ended"}
    for lang in (fields.get("left_lang"), fields.get("right_lang")):
        if lang is not None and lang not in TRANSLATE_LANGUAGES:
            raise HTTPException(status_code=400, detail=t("interpreter.badTarget", locale))
    if body.ended is not None:
        fields["ended_at"] = repo.now() if body.ended else None
    updated = repo.update_session(session["id"], **fields) if fields else session
    return service.state(updated or session)


@router.delete("/interpreter/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not repo.delete_session(session_id, current_user.get("user_id", 0)):
        raise HTTPException(status_code=404, detail=t("interpreter.sessionUnknown", locale))


@router.put("/interpreter/sessions/{session_id}/turns/{turn_id}")
def put_turn(
    session_id: str,
    turn_id: str,
    body: TurnIn,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    session = _own(session_id, current_user, locale)
    return service.save_turn(session, {"id": turn_id, **body.model_dump()}, locale)
