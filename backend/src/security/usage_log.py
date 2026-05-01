"""LLM-Usage-Logging in eigene DB-Tabelle (``aia_llm_usage_log``).

Pro LLM-Request 1 Zeile mit User, Endpoint, Provider, Tokens (best effort),
Dauer und Status. Wird vom Tagesalarm gegen rolling 7d-Average geprüft, um
plötzliche Verbrauchssprünge zu erkennen - ohne dass eine fixe Schwelle
gesetzt werden muss (Plattform skaliert sich selbst ein).

Langfuse hat die exakte Wahrheit für Token-Tracing. Diese Tabelle ist die
schnelle, lokal aggregierbare Alternative für Alarms und Admin-Dashboards.

Fire-and-forget: bei DB-Fehler nur Warnung loggen, niemals den eigentlichen
Request scheitern lassen.
"""

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
    """Schreibt eine Zeile in ``aia_llm_usage_log``. Fail-safe.

    ``status``: ``"ok"`` | ``"error"`` | ``"rate_limited"``.
    """
    if user_id <= 0:
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
