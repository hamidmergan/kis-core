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


def enroll_student(
    module_id: int, user_id: int, enrolled_until: datetime | None,
    link_id: int | None = None,
) -> int | None:
    """Enroll student. Returns enrollment id, or None if already enrolled for this link."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_enrollments (module_id, user_id, link_id, enrolled_until)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (module_id, user_id, link_id) DO NOTHING
                   RETURNING id""",
                (module_id, user_id, link_id, enrolled_until),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0] if row else None

def is_student_enrolled(module_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM aia_enrollments WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            return cur.fetchone() is not None

def get_enrollment(module_id: int, user_id: int, link_id: int | None = None) -> dict | None:
    """Get a specific enrollment by module, user, and optionally link."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if link_id is not None:
                cur.execute(
                    "SELECT * FROM aia_enrollments WHERE module_id = %s AND user_id = %s AND link_id = %s",
                    (module_id, user_id, link_id),
                )
            else:
                cur.execute(
                    "SELECT * FROM aia_enrollments WHERE module_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1",
                    (module_id, user_id),
                )
            row = cur.fetchone()
    return dict(row) if row else None

def get_enrollment_by_id(enrollment_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_enrollments WHERE id = %s", (enrollment_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_module_by_enroll_code(code: str) -> dict | None:
    """Legacy: check both access_links and modules table."""
    result = get_module_by_access_link_code(code)
    if result:
        return result[0]  # return just the module for backward compat
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM aia_modules
                   WHERE enroll_code = %s AND enroll_code_expires > NOW()""",
                (code,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


# --- KI Tutor: Sources ---

