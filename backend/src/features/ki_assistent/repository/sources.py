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


def create_ki_tutor_source(
    module_id: int, uuid: str, filename: str, file_path: str, file_type: str
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_sources
                   (module_id, uuid, filename, file_path, file_type)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id""",
                (module_id, uuid, filename, file_path, file_type),
            )
            source_id = cur.fetchone()[0]
        conn.commit()
    return source_id

def get_ki_tutor_source(uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_sources WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_ki_tutor_sources_by_module(module_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM ki_tutor_sources WHERE module_id = %s ORDER BY created_at DESC",
                (module_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def list_ki_tutor_modules_with_stale_fingerprint(current_fingerprint: str) -> list[dict]:
    """Return modules (with owner name) whose stored fingerprint differs from current.

    Modules without a fingerprint (never indexed) are ignored.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT m.id, m.uuid, m.title, u.display_name AS owner
                   FROM ki_tutor_modules m
                   JOIN ki_tutor_sources s ON s.module_id = m.id
                   LEFT JOIN users u ON u.id = m.user_id
                   WHERE m.embedding_fingerprint IS NOT NULL
                     AND m.embedding_fingerprint <> %s
                   ORDER BY m.title ASC""",
                (current_fingerprint,),
            )
            return [dict(row) for row in cur.fetchall()]

def get_all_ki_tutor_sources() -> list[dict]:
    """Return every KI-Assistent source across all modules — used for global re-indexing."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_sources ORDER BY id ASC")
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def update_ki_tutor_source_status(
    uuid: str,
    status: str,
    chunk_count: int | None = None,
    embedding_model: str | None = None,
    error_message: str | None = None,
    duration: float | None = None,
    language: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_sources
                   SET status = %s,
                       chunk_count = COALESCE(%s, chunk_count),
                       embedding_model = COALESCE(%s, embedding_model),
                       error_message = COALESCE(%s, error_message),
                       duration = COALESCE(%s, duration),
                       language = COALESCE(%s, language)
                   WHERE uuid = %s""",
                (status, chunk_count, embedding_model, error_message, duration, language, uuid),
            )
        conn.commit()

def update_ki_tutor_source_toc(uuid: str, toc: list[dict]) -> None:
    import json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ki_tutor_sources SET toc = %s WHERE uuid = %s",
                (json.dumps(toc), uuid),
            )
        conn.commit()

def delete_ki_tutor_source(uuid: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_sources WHERE uuid = %s", (uuid,))
        conn.commit()

def delete_ki_tutor_chunks_by_source(source_id: int) -> None:
    """Remove all chunks for a source (used when retrying a failed indexing run)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_chunks WHERE source_id = %s", (source_id,))
        conn.commit()

def reset_ki_tutor_source_for_retry(uuid: str) -> None:
    """Reset a failed source to pending state and clear the error message."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_sources
                   SET status = 'pending', error_message = NULL, chunk_count = 0
                   WHERE uuid = %s""",
                (uuid,),
            )
        conn.commit()


# --- KI Tutor: Chunks ---

