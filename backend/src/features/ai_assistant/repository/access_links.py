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


def create_access_link(module_id: int, code: str, expires_at: datetime | None) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """INSERT INTO aia_access_links (module_id, code, expires_at)
                   VALUES (%s, %s, %s)
                   RETURNING id, module_id, code, expires_at, created_at""",
                (module_id, code, expires_at),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row)

def get_access_links_by_module(module_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, module_id, code, expires_at, created_at
                   FROM aia_access_links
                   WHERE module_id = %s
                   ORDER BY created_at ASC""",
                (module_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def delete_access_link(link_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_access_links WHERE id = %s", (link_id,))
        conn.commit()

def get_module_by_access_link_code(code: str) -> tuple[dict, dict] | None:
    """Return (module, link) tuple if code is valid and not expired."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.*, al.id AS link_id, al.expires_at AS link_expires_at
                   FROM aia_access_links al
                   JOIN aia_modules m ON m.id = al.module_id
                   WHERE al.code = %s AND (al.expires_at IS NULL OR al.expires_at > NOW())""",
                (code,),
            )
            row = cur.fetchone()
    if not row:
        return None
    row = dict(row)
    link = {"id": row.pop("link_id"), "expires_at": row.pop("link_expires_at")}
    return row, link


# --- KI Tutor: Enrollments ---

