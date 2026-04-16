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


def get_kia_notes(module_id: int, user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, content, created_at FROM kia_notes WHERE module_id = %s AND user_id = %s ORDER BY created_at DESC",
                (module_id, user_id),
            )
            return [dict(r) for r in cur.fetchall()]

def count_kia_notes(module_id: int, user_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM kia_notes WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            return int(cur.fetchone()[0])

def create_kia_note(module_id: int, user_id: int, content: str) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO kia_notes (module_id, user_id, content) VALUES (%s, %s, %s) RETURNING id, content, created_at",
                (module_id, user_id, content),
            )
            row = dict(cur.fetchone())
        conn.commit()
        return row

def delete_kia_note(note_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM kia_notes WHERE id = %s AND user_id = %s",
                (note_id, user_id),
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted


# --- KI Tutor: Paragraph Summaries ---

