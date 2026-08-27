"""Shortens on too much context and retries exactly once."""

from __future__ import annotations

from loguru import logger

from src.services import model_limits


def create_with_shrink(client, *, model: str, messages: list[dict], endpoint: str = "tool", **kwargs):
    """A model call with shortening and a second attempt."""
    try:
        antwort = client.chat.completions.create(model=model, messages=messages, **kwargs)
        _mitschreiben(endpoint, client, model, antwort)
        return antwort
    except Exception as e:  # noqa: BLE001 — die Absage IST die Information
        provider_id = _provider_id_for_chat()
        if not provider_id:
            raise
        fenster = model_limits.learn_from_error(provider_id, model, e)
        if not fenster:
            raise
        gekuerzt = model_limits.fit_messages(
            messages, model_limits.context_chars(fenster, model_limits.TOOL_SHARE),
        )
        logger.warning(
            "Werkzeug-Kontext war zu gross fuer {}, auf {} Token gekuerzt und wiederholt",
            model, fenster,
        )
        antwort = client.chat.completions.create(model=model, messages=gekuerzt, **kwargs)
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


def _provider_id_for_chat() -> int | None:
    """Id of the provider serving the chat route."""
    try:
        from src.services import feature_router
        return (feature_router.resolve("chat").provider or {}).get("id")
    except Exception as e:  # noqa: BLE001 — ohne Kennung wird eben nicht gelernt
        logger.debug("Anbieter der Chat-Route nicht ermittelbar: {}", e)
        return None
