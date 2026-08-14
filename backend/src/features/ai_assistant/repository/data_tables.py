import os
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def create_aia_data_table(workspace_id: int, user_id: int, source_ids: list[int]) -> int:
    """Create a pending data_table record, return its id."""
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_data_tables (workspace_id, user_id, source_ids, status)
                   VALUES (%s, %s, %s, 'pending') RETURNING id""",
                (workspace_id, user_id, _json.dumps(source_ids)),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]

def update_aia_data_table(
    data_table_id: int,
    status: str,
    title: str | None = None,
    table_data: dict | None = None,
    sources: list | None = None,
    error: str | None = None,
) -> None:
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_data_tables
                   SET status = %s, title = %s, table_data = %s, sources = %s, error = %s, updated_at = NOW()
                   WHERE id = %s""",
                (status, title,
                 _json.dumps(table_data) if table_data else None,
                 _json.dumps(sources) if sources else None,
                 error, data_table_id),
            )
        conn.commit()

def get_aia_data_table(data_table_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_data_tables WHERE id = %s", (data_table_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_latest_aia_data_table(workspace_id: int, user_id: int) -> dict | None:
    """Get the most recent data_table for a workspace/user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM aia_data_tables
                   WHERE workspace_id = %s AND user_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None

def get_aia_data_tables_by_workspace(workspace_id: int, user_id: int) -> list[dict]:
    """Get all successful data_tables for a workspace/user (without table_data for listing)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, status, title, sources, created_at
                   FROM aia_data_tables
                   WHERE workspace_id = %s AND user_id = %s AND status = 'success'
                   ORDER BY created_at DESC""",
                (workspace_id, user_id),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def delete_aia_data_table(data_table_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_data_tables WHERE id = %s", (data_table_id,))
        conn.commit()


# --- KI Tutor: Chunks by Source ---

