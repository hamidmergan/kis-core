"""Database access to provider_checks, the last real call per provider and function."""

from datetime import datetime
from typing import Optional

import psycopg2.extras

from src.core.db.pool import get_connection


def list_checks() -> dict[tuple[int, str], dict]:
    """Every stored result, keyed by provider and function."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT provider_id, feature, status, error, checked_at FROM provider_checks")
            out = {}
            for r in cur.fetchall():
                d = dict(r)
                if isinstance(d["checked_at"], datetime):
                    d["checked_at"] = d["checked_at"].isoformat()
                out[(d["provider_id"], d["feature"])] = d
            return out


def set_check(provider_id: int, feature: str, *, status: str, error: Optional[str]) -> None:
    """Stores the result of one real call, replacing the previous one."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO provider_checks (provider_id, feature, status, error, checked_at)
                   VALUES (%s, %s, %s, %s, NOW())
                   ON CONFLICT (provider_id, feature)
                   DO UPDATE SET status = EXCLUDED.status, error = EXCLUDED.error, checked_at = NOW()""",
                (provider_id, feature, status, error),
            )
            conn.commit()


def clear_feature(feature: str) -> None:
    """Drops the stored results of one function, so the next dropdown checks the new models."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM provider_checks WHERE feature = %s", (feature,))
            conn.commit()
