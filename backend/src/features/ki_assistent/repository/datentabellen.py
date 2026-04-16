import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection
from src.core.db._common import _notify_job_update, _de_date_to_utc


def create_ki_tutor_datentabelle(module_id: int, user_id: int, source_ids: list[int]) -> int:
    """Create a pending datentabelle record, return its id."""
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_datentabellen (module_id, user_id, source_ids, status)
                   VALUES (%s, %s, %s, 'pending') RETURNING id""",
                (module_id, user_id, _json.dumps(source_ids)),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]

def update_ki_tutor_datentabelle(
    datentabelle_id: int,
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
                """UPDATE ki_tutor_datentabellen
                   SET status = %s, title = %s, table_data = %s, sources = %s, error = %s, updated_at = NOW()
                   WHERE id = %s""",
                (status, title,
                 _json.dumps(table_data) if table_data else None,
                 _json.dumps(sources) if sources else None,
                 error, datentabelle_id),
            )
        conn.commit()

def get_ki_tutor_datentabelle(datentabelle_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_datentabellen WHERE id = %s", (datentabelle_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_latest_ki_tutor_datentabelle(module_id: int, user_id: int) -> dict | None:
    """Get the most recent datentabelle for a module/user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM ki_tutor_datentabellen
                   WHERE module_id = %s AND user_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (module_id, user_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None

def get_ki_tutor_datentabellen_by_module(module_id: int, user_id: int) -> list[dict]:
    """Get all successful datentabellen for a module/user (without table_data for listing)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, status, title, sources, created_at
                   FROM ki_tutor_datentabellen
                   WHERE module_id = %s AND user_id = %s AND status = 'success'
                   ORDER BY created_at DESC""",
                (module_id, user_id),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def delete_ki_tutor_datentabelle(datentabelle_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_datentabellen WHERE id = %s", (datentabelle_id,))
        conn.commit()


# --- KI Tutor: Chunks by Source ---

