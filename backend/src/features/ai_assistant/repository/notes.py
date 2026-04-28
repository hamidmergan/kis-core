import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
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
                "SELECT id, title, content, source_uuids, source_pages, popup_selection, created_at "
                "FROM kia_notes WHERE module_id = %s AND user_id = %s ORDER BY created_at DESC",
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

def create_kia_note(
    module_id: int,
    user_id: int,
    content: str,
    title: Optional[str] = None,
    source_uuids: Optional[list[str]] = None,
    source_pages: Optional[list[dict]] = None,
    popup_selection: Optional[dict] = None,
) -> dict:
    clean_title = title.strip() if title else None
    if clean_title == "":
        clean_title = None
    clean_uuids: Optional[list[str]] = None
    if source_uuids:
        seen: set[str] = set()
        clean_uuids = []
        for u in source_uuids:
            if isinstance(u, str) and u and u not in seen:
                seen.add(u)
                clean_uuids.append(u)
        if not clean_uuids:
            clean_uuids = None
    pages_json = json.dumps(source_pages) if source_pages else None
    popup_json = json.dumps(popup_selection) if popup_selection else None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO kia_notes (module_id, user_id, content, title, source_uuids, source_pages, popup_selection) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id, title, content, source_uuids, source_pages, popup_selection, created_at",
                (module_id, user_id, content, clean_title,
                 json.dumps(clean_uuids) if clean_uuids is not None else None,
                 pages_json, popup_json),
            )
            row = dict(cur.fetchone())
        conn.commit()
        return row

def update_kia_note_title(note_id: int, user_id: int, title: Optional[str]) -> bool:
    clean = title.strip() if title else None
    if clean == "":
        clean = None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE kia_notes SET title = %s WHERE id = %s AND user_id = %s",
                (clean, note_id, user_id),
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated

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

