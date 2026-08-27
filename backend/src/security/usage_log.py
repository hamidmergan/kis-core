"""One row per model request, for daily reports and the admin area."""

from typing import Optional

from loguru import logger

from src.core.db.pool import get_connection


def log_request(
    user_id: int,
    endpoint: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    duration_ms: Optional[int] = None,
    status: str = "ok",
) -> None:
    """Writes a row into the usage log, errors stay without consequence."""
    if user_id == 0:
        return

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO aia_llm_usage_log
                       (user_id, endpoint, provider, model, tokens_in, tokens_out, duration_ms, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (user_id, endpoint, provider, model, tokens_in, tokens_out, duration_ms, status),
                )
            conn.commit()
    except Exception as e:
        logger.warning(
            "usage_log insert fehlgeschlagen (user={}, endpoint={}): {}",
            user_id, endpoint, e,
        )


def log_llm_response(endpoint: str, client, response) -> None:
    """Records the consumption of an answer, without a user id and fail-safe."""
    try:
        nutzung = getattr(response, "usage", None)
        log_request(
            user_id=-1,
            endpoint=endpoint,
            provider=getattr(client, "_provider", None),
            model=getattr(client, "_model", None),
            tokens_in=getattr(nutzung, "prompt_tokens", None),
            tokens_out=getattr(nutzung, "completion_tokens", None),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Verbrauch nicht mitgeschrieben ({}): {}", endpoint, e)
