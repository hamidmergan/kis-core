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


def create_ki_tutor_mindmap(module_id: int, user_id: int, source_ids: list[int]) -> int:
    """Create a pending mindmap record, return its id."""
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_mindmaps (module_id, user_id, source_ids, status)
                   VALUES (%s, %s, %s, 'pending') RETURNING id""",
                (module_id, user_id, _json.dumps(source_ids)),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]

def update_ki_tutor_mindmap(mindmap_id: int, status: str, mindmap: dict | None = None, error: str | None = None) -> None:
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_mindmaps
                   SET status = %s, mindmap = %s, error = %s, updated_at = NOW()
                   WHERE id = %s""",
                (status, _json.dumps(mindmap) if mindmap else None, error, mindmap_id),
            )
        conn.commit()

def get_ki_tutor_mindmap(mindmap_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_mindmaps WHERE id = %s", (mindmap_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_latest_ki_tutor_mindmap(module_id: int, user_id: int) -> dict | None:
    """Get the most recent mindmap for a module/user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM ki_tutor_mindmaps
                   WHERE module_id = %s AND user_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (module_id, user_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None

def get_all_ki_tutor_mindmaps(module_id: int, user_id: int) -> list[dict]:
    """Get all successful mindmaps for a module/user, newest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, status, created_at, mindmap
                   FROM ki_tutor_mindmaps
                   WHERE module_id = %s AND user_id = %s AND status = 'success'
                   ORDER BY created_at DESC""",
                (module_id, user_id),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]

def delete_ki_tutor_mindmap(mindmap_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_mindmaps WHERE id = %s", (mindmap_id,))
        conn.commit()


# --- KI Tutor: Datentabellen ---

