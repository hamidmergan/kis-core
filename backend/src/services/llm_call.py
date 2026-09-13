"""One model call for the tools, with the consumption written to the usage log.

No shrinking on refusal: a refusal cannot be told apart reliably enough from a
rate limit or an outage, and a misread size used to be stored for good. The
context size is the admin setting alone.
"""

from __future__ import annotations

from loguru import logger


def create_logged(client, *, model: str, messages: list[dict], endpoint: str = "tool", **kwargs):
    """A model call whose consumption lands in the usage log."""
    antwort = client.chat.completions.create(model=model, messages=messages, **kwargs)
    _mitschreiben(endpoint, client, model, antwort)
    return antwort


def _mitschreiben(endpoint: str, client, model: str, antwort) -> None:
    """Writes the consumption to the usage log, cleanly or not at all."""
    try:
        from src.security.usage_log import log_request
        nutzung = getattr(antwort, "usage", None)
        log_request(
            user_id=-1,
            endpoint=endpoint,
            provider=getattr(client, "_provider", None),
            model=model,
            tokens_in=getattr(nutzung, "prompt_tokens", None),
            tokens_out=getattr(nutzung, "completion_tokens", None),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Verbrauch nicht mitgeschrieben ({}): {}", endpoint, e)
