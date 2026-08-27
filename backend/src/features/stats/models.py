"""Model numbers from the usage log, so far only the chat writes to it."""
from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection


def model_usage(days: int | None = None) -> dict:
    """Requests and tokens, optionally only the last N days."""
    wo = "WHERE ts >= NOW() - (%s || ' days')::interval" if days else ""
    args = (days,) if days else ()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            return {
                "totals": _totals(cur, wo, args),
                "per_month": _per_month(cur, wo, args),
                "per_model": _per_model(cur, wo, args),
                "endpoints": _endpoints(cur, wo, args),
            }


def _totals(cur, wo: str, args: tuple) -> dict:
    cur.execute(
        f"""SELECT COUNT(*) AS anfragen,
                   COALESCE(SUM(tokens_in), 0)  AS rein,
                   COALESCE(SUM(tokens_out), 0) AS raus
            FROM aia_llm_usage_log {wo}""",
        args,
    )
    r = cur.fetchone()
    return {
        "requests": r["anfragen"],
        "tokens_in": int(r["rein"]),
        "tokens_out": int(r["raus"]),
    }


def _per_month(cur, wo: str, args: tuple) -> list[dict]:
    cur.execute(
        f"""SELECT to_char(date_trunc('month', ts), 'MM/YY') AS monat,
                   date_trunc('month', ts) AS sortier,
                   COUNT(*) AS anfragen
            FROM aia_llm_usage_log {wo}
            GROUP BY 1, 2 ORDER BY 2""",
        args,
    )
    return [{"month": r["monat"], "requests": r["anfragen"]} for r in cur.fetchall()]


def _per_model(cur, wo: str, args: tuple) -> list[dict]:
    """Per model, excluding those without tokens: Whisper and speech count none."""
    cur.execute(
        f"""SELECT COALESCE(model, 'unbekannt') AS modell,
                   COALESCE(provider, 'unbekannt') AS anbieter,
                   COUNT(*) AS anfragen,
                   COALESCE(SUM(tokens_in), 0) + COALESCE(SUM(tokens_out), 0) AS tokens
            FROM aia_llm_usage_log {wo}
            GROUP BY 1, 2
            HAVING COALESCE(SUM(tokens_in), 0) + COALESCE(SUM(tokens_out), 0) > 0
            ORDER BY 3 DESC""",
        args,
    )
    return [
        {
            "model": r["modell"],
            "provider": r["anbieter"],
            "requests": r["anfragen"],
            "tokens": int(r["tokens"]),
        }
        for r in cur.fetchall()
    ]


def _endpoints(cur, wo: str, args: tuple) -> list[dict]:
    """Where the requests come from, while only 'chat' shows up the gap is still open."""
    cur.execute(
        f"""SELECT endpoint, COUNT(*) AS anfragen
            FROM aia_llm_usage_log {wo}
            GROUP BY 1 ORDER BY 2 DESC""",
        args,
    )
    return [{"endpoint": r["endpoint"], "requests": r["anfragen"]} for r in cur.fetchall()]
