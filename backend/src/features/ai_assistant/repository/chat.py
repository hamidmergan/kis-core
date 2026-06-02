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


def save_aia_message(
    workspace_id: int,
    user_id: int,
    role: str,
    content: str,
    source_pages: list | dict | None = None,
    enrollment_id: int | None = None,
    source_qmap: list | None = None,
    aborted: bool = False,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_messages
                   (workspace_id, user_id, role, content, source_pages, enrollment_id, source_qmap, aborted)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    workspace_id,
                    user_id,
                    role,
                    content,
                    json.dumps(source_pages) if source_pages is not None else None,
                    enrollment_id,
                    json.dumps(source_qmap) if source_qmap is not None else None,
                    aborted,
                ),
            )
        conn.commit()

def delete_aia_messages(workspace_id: int, user_id: int, enrollment_id: int | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if enrollment_id is not None:
                cur.execute(
                    "DELETE FROM aia_messages WHERE workspace_id = %s AND user_id = %s AND enrollment_id = %s",
                    (workspace_id, user_id, enrollment_id),
                )
            else:
                cur.execute(
                    "DELETE FROM aia_messages WHERE workspace_id = %s AND user_id = %s AND enrollment_id IS NULL",
                    (workspace_id, user_id),
                )
        conn.commit()

def get_aia_messages(
    workspace_id: int,
    user_id: int,
    limit: int = 20,
    enrollment_id: int | None = None,
    include_aborted: bool = True,
) -> list[dict]:
    """Fetch chat history (for the chat UI). Pass include_aborted=False to drop
    cancelled half-answers from the result."""
    aborted_filter = "" if include_aborted else " AND aborted = FALSE"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if enrollment_id is not None:
                cur.execute(
                    f"""SELECT * FROM aia_messages
                       WHERE workspace_id = %s AND user_id = %s AND enrollment_id = %s{aborted_filter}
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (workspace_id, user_id, enrollment_id, limit),
                )
            else:
                cur.execute(
                    f"""SELECT * FROM aia_messages
                       WHERE workspace_id = %s AND user_id = %s AND enrollment_id IS NULL{aborted_filter}
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (workspace_id, user_id, limit),
                )
            rows = cur.fetchall()
    return list(reversed([dict(row) for row in rows]))

def get_aia_user_settings(workspace_id: int, user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM aia_user_settings WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
    if row:
        return dict(row)
    return {"chat_lang": "de", "studio_enabled": True, "language_training_active": False}

def upsert_aia_user_settings(
    workspace_id: int, user_id: int, chat_lang: str, studio_enabled: bool, language_training_active: bool
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_user_settings (workspace_id, user_id, chat_lang, studio_enabled, language_training_active)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (workspace_id, user_id)
                   DO UPDATE SET chat_lang = EXCLUDED.chat_lang,
                                 studio_enabled = EXCLUDED.studio_enabled,
                                 language_training_active = EXCLUDED.language_training_active""",
                (workspace_id, user_id, chat_lang, studio_enabled, language_training_active),
            )
        conn.commit()


# --- KI Tutor: Notes ---

