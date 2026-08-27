"""A model call whose answer should be JSON, the JSON mode is probed once."""

import asyncio

from fastapi import HTTPException
from loguru import logger

from src.i18n import t

# Probed once per process instead of again on every call.
_json_mode_supported = True


def _rejects_json_mode(exc: Exception) -> bool:
    """True when the provider explicitly rejected response_format."""
    if getattr(exc, "status_code", None) != 400:
        return False
    text = str(exc).lower()
    return "response_format" in text or "json" in text


def _create(llm, messages: list[dict], *, json_mode: bool):
    kwargs = {
        "model": llm._model,
        "messages": messages,
        "temperature": 0.4,
        **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return llm._client.chat.completions.create(**kwargs)


def call_json_llm(llm, messages: list[dict]):
    """One run, in JSON mode where the provider can do it."""
    global _json_mode_supported
    if _json_mode_supported:
        try:
            return _create(llm, messages, json_mode=True)
        except Exception as exc:
            if not _rejects_json_mode(exc):
                raise
            logger.warning("JSON-Modus vom Anbieter abgelehnt, dieser Prozess "
                           "fragt ab jetzt ohne: {}", exc)
            _json_mode_supported = False
    return _create(llm, messages, json_mode=False)


async def ask_json(llm, messages: list[dict], *, locale: str, what: str) -> str:
    """The call in a thread, with a readable refusal on failure."""
    try:
        response = await asyncio.to_thread(call_json_llm, llm, messages)
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("{} LLM call failed: {}", what, exc)
        raise HTTPException(status_code=502,
                            detail=t("ai.languageDiagnosis.llmUnavailable", locale))
