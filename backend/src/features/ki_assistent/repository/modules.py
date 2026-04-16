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


def create_kia_module(user_id: int, title: str, description: str | None) -> str:
    import uuid as _uuid
    module_uuid = str(_uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO kia_modules (uuid, user_id, title, description)
                   VALUES (%s, %s, %s, %s)""",
                (module_uuid, user_id, title, description),
            )
        conn.commit()
    return module_uuid

def get_kia_module(uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM kia_modules WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_kia_module_by_id(id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM kia_modules WHERE id = %s", (id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_kia_modules_by_user(user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM kia_modules WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def get_kia_modules_for_student(user_id: int) -> list[dict]:
    """Return modules with enrollment info. Same module can appear multiple times (different links)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.*, e.id AS enrollment_id, e.link_id, e.enrolled_until,
                          al.code AS link_code, al.expires_at AS link_expires_at
                   FROM kia_modules m
                   JOIN kia_enrollments e ON e.module_id = m.id
                   LEFT JOIN kia_access_links al ON al.id = e.link_id
                   WHERE e.user_id = %s AND m.is_active = TRUE
                   ORDER BY e.created_at DESC""",
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def update_kia_module(
    uuid: str, title: str, description: str | None, is_active: bool
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE kia_modules
                   SET title = %s, description = %s, is_active = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (title, description, is_active, uuid),
            )
        conn.commit()

def update_kia_module_status(
    uuid: str,
    status: str,
    embedding_model: str | None = None,
    embedding_fingerprint: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE kia_modules
                   SET status = %s,
                       embedding_model = COALESCE(%s, embedding_model),
                       embedding_fingerprint = COALESCE(%s, embedding_fingerprint),
                       updated_at = NOW()
                   WHERE uuid = %s""",
                (status, embedding_model, embedding_fingerprint, uuid),
            )
        conn.commit()

def set_kia_module_enroll_code(
    uuid: str, code: str, expires_at: datetime | None
) -> None:
    """Legacy: kept for backward compat. Prefer create_access_link."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE kia_modules
                   SET enroll_code = %s, enroll_code_expires = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (code, expires_at, uuid),
            )
        conn.commit()

def delete_kia_module(uuid: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kia_modules WHERE uuid = %s", (uuid,))
        conn.commit()


# --- KI Tutor: Access Links ---

