"""Shared helpers for KI-Assistent Celery tasks."""

import re

from langfuse.decorators import langfuse_context


def _format_ts(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


def _language_label(locale: str) -> str:
    """Map a locale to the target language name used in generation prompts."""
    return "English" if (locale or "").lower().startswith("en") else "German"


def _get_llm_client():
    """Return (client, model, provider) using the configured LLM provider."""
    from langfuse.openai import OpenAI
    from src.dependencies import _resolve_llm_provider
    _api_key, _base_url, _model, _provider = _resolve_llm_provider()
    from src.features.ai_assistant.tasks._retry import RetryingClient
    # max_retries=0 bleibt: die eingebaute Wiederholung des SDK unterscheidet nicht
    # zwischen einer abgerissenen Verbindung und einer Absage wegen Überlastung, und
    # eine 429 nachzuschlagen verschärft den hochschulweit geteilten Engpass. Die
    # Unterscheidung trifft RetryingClient.
    client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=120)
    langfuse_context.update_current_observation(
        metadata={"provider": _provider, "base_url": _base_url, "model": _model},
    )
    return RetryingClient(client), _model, _provider


def _clean_llm_json(text: str) -> str:
    """Strip markdown fences and leading/trailing whitespace from LLM JSON output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
