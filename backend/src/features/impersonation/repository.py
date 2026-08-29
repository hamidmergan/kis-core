"""The record of who was inside whose account."""

import psycopg2.extras

from src.core.db.pool import get_connection


def start_entry(
    *,
    actor_user_id: int,
    actor_username: str,
    target_user_id: int,
    target_username: str,
) -> int:
    """Opens an entry and returns its id, the end is filled in later."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO impersonation_log
                       (actor_user_id, actor_username, target_user_id, target_username)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id""",
                (actor_user_id, actor_username, target_user_id, target_username),
            )
            entry_id = cur.fetchone()[0]
        conn.commit()
        return entry_id


def end_entry(entry_id: int, reason: str) -> None:
    """Stamps the end, an entry that is already closed keeps its first end."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE impersonation_log
                      SET ended_at = NOW(), ended_reason = %s
                    WHERE id = %s AND ended_at IS NULL""",
                (reason, entry_id),
            )
        conn.commit()


def list_entries(limit: int = 100, offset: int = 0) -> list[dict]:
    """Newest first, for the list in the admin area."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM impersonation_log
                   ORDER BY started_at DESC
                   LIMIT %s OFFSET %s""",
                (limit, offset),
            )
            return [dict(row) for row in cur.fetchall()]


def count_entries() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM impersonation_log")
            return int(cur.fetchone()[0])
