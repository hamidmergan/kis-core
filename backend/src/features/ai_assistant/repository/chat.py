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


def save_kia_message(
    module_id: int,
    user_id: int,
    role: str,
    content: str,
    source_pages: list | dict | None = None,
    enrollment_id: int | None = None,
    source_qmap: list | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO kia_messages
                   (module_id, user_id, role, content, source_pages, enrollment_id, source_qmap)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    module_id,
                    user_id,
                    role,
                    content,
                    json.dumps(source_pages) if source_pages is not None else None,
                    enrollment_id,
                    json.dumps(source_qmap) if source_qmap is not None else None,
                ),
            )
        conn.commit()

def delete_kia_messages(module_id: int, user_id: int, enrollment_id: int | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if enrollment_id is not None:
                cur.execute(
                    "DELETE FROM kia_messages WHERE module_id = %s AND user_id = %s AND enrollment_id = %s",
                    (module_id, user_id, enrollment_id),
                )
            else:
                cur.execute(
                    "DELETE FROM kia_messages WHERE module_id = %s AND user_id = %s AND enrollment_id IS NULL",
                    (module_id, user_id),
                )
        conn.commit()

def get_kia_messages(
    module_id: int, user_id: int, limit: int = 20, enrollment_id: int | None = None
) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if enrollment_id is not None:
                cur.execute(
                    """SELECT * FROM kia_messages
                       WHERE module_id = %s AND user_id = %s AND enrollment_id = %s
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (module_id, user_id, enrollment_id, limit),
                )
            else:
                cur.execute(
                    """SELECT * FROM kia_messages
                       WHERE module_id = %s AND user_id = %s AND enrollment_id IS NULL
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (module_id, user_id, limit),
                )
            rows = cur.fetchall()
    return list(reversed([dict(row) for row in rows]))

def get_kia_user_settings(module_id: int, user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM kia_user_settings WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            row = cur.fetchone()
    if row:
        return dict(row)
    return {"chat_lang": "de", "studio_enabled": True, "sprachtraining_active": False}

def upsert_kia_user_settings(
    module_id: int, user_id: int, chat_lang: str, studio_enabled: bool, sprachtraining_active: bool
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO kia_user_settings (module_id, user_id, chat_lang, studio_enabled, sprachtraining_active)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (module_id, user_id)
                   DO UPDATE SET chat_lang = EXCLUDED.chat_lang,
                                 studio_enabled = EXCLUDED.studio_enabled,
                                 sprachtraining_active = EXCLUDED.sprachtraining_active""",
                (module_id, user_id, chat_lang, studio_enabled, sprachtraining_active),
            )
        conn.commit()


# --- KI Tutor: Notes ---

