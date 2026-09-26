import json
import os
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def create_aia_source(
    workspace_id: int, uuid: str, filename: str, file_path: str, file_type: str,
    source_url: str | None = None, content_hash: str | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_sources
                   (workspace_id, uuid, filename, file_path, file_type, source_url, content_hash)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (workspace_id, uuid, filename, file_path, file_type, source_url, content_hash),
            )
            source_id = cur.fetchone()[0]
        conn.commit()
    return source_id


def get_aia_source_by_content_hash(workspace_id: int, content_hash: str) -> dict | None:
    """The same file already lies in this course room, recognised by its content."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM aia_sources
                   WHERE workspace_id = %s AND content_hash = %s
                   ORDER BY id LIMIT 1""",
                (workspace_id, content_hash),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_aia_sources_by_last_used(workspace_id: int) -> list[dict]:
    """Least recently used first, the order the podcast store evicts in."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM aia_sources WHERE workspace_id = %s
                   ORDER BY last_used_at ASC, id ASC""",
                (workspace_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def touch_aia_sources_used(uuids: list[str]) -> None:
    """Marks sources as used by this run so eviction takes the forgotten ones."""
    if not uuids:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_sources SET last_used_at = NOW() WHERE uuid = ANY(%s)",
                (list(uuids),),
            )
        conn.commit()

def get_aia_source(uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_sources WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_aia_source_by_id(source_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_sources WHERE id = %s", (source_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_aia_sources_by_workspace(workspace_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM aia_sources WHERE workspace_id = %s ORDER BY created_at DESC",
                (workspace_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def list_aia_workspaces_with_stale_fingerprint(current_fingerprint: str) -> list[dict]:
    """Course rooms whose stored fingerprint differs from the current one."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT m.id, m.uuid, m.title, u.display_name AS owner
                   FROM aia_workspaces m
                   JOIN aia_sources s ON s.workspace_id = m.id
                   LEFT JOIN users u ON u.id = m.user_id
                   WHERE m.embedding_fingerprint IS NOT NULL
                     AND m.embedding_fingerprint <> %s
                   ORDER BY m.title ASC""",
                (current_fingerprint,),
            )
            return [dict(row) for row in cur.fetchall()]

def get_all_aia_sources() -> list[dict]:
    """Return every KI-Assistent source across all workspaces - used for global re-indexing."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_sources ORDER BY id ASC")
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def list_all_sources_for_eval() -> list[dict]:
    """Eval/diagnostics only: every source row (id, filename, file_path)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, filename, file_path, workspace_id FROM aia_sources")
            return [dict(r) for r in cur.fetchall()]

def update_aia_source_status(
    uuid: str,
    status: str,
    chunk_count: int | None = None,
    embedding_model: str | None = None,
    error_message: str | None = None,
    duration: float | None = None,
    language: str | None = None,
) -> None:
    # Final states clear the progress, otherwise an old step label lingers.
    progress_clause = ", progress = NULL" if status in ("ready", "failed") else ""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE aia_sources
                    SET status = %s,
                        chunk_count = COALESCE(%s, chunk_count),
                        embedding_model = COALESCE(%s, embedding_model),
                        error_message = COALESCE(%s, error_message),
                        duration = COALESCE(%s, duration),
                        language = COALESCE(%s, language)
                        {progress_clause}
                    WHERE uuid = %s""",
                (status, chunk_count, embedding_model, error_message, duration, language, uuid),
            )
        conn.commit()


def clear_aia_source_progress(uuid: str) -> None:
    """Sets the progress to NULL as soon as ingest is done."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_sources SET progress = NULL WHERE uuid = %s",
                (uuid,),
            )
        conn.commit()


def update_aia_source_progress(
    uuid: str,
    stage: str,
    page: int | None = None,
    total: int | None = None,
) -> None:
    """Records the running ingest step so the interface can show it."""
    payload: dict = {"stage": stage}
    if page is not None:
        payload["page"] = page
    if total is not None:
        payload["total"] = total
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_sources SET progress = %s WHERE uuid = %s",
                (json.dumps(payload), uuid),
            )
        conn.commit()

def update_aia_source_ocr_info(uuid: str, ocr_info: dict | None) -> None:
    """Records how text recognition went, None clears the column."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_sources SET ocr_info = %s WHERE uuid = %s",
                (json.dumps(ocr_info) if ocr_info else None, uuid),
            )
        conn.commit()


def update_aia_source_summary(uuid: str, summary: str) -> None:
    """Store the per-source DOC SUMMARY (built at ingest, map-reduce over chunks)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_sources SET summary = %s WHERE uuid = %s",
                (summary, uuid),
            )
        conn.commit()

def delete_aia_source(uuid: str) -> None:
    """Deletes a source, finished exercise sets get their content beforehand, the schedule loses its hits."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, workspace_id FROM aia_sources WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    if row:
        from src.features.ai_assistant.repository.exercise_pool import materialize_pool_items
        from src.features.ai_assistant.repository.schedule import remove_source_from_schedule
        materialize_pool_items(row[0])
        remove_source_from_schedule(row[1], uuid)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_sources WHERE uuid = %s", (uuid,))
        conn.commit()

def delete_aia_chunks_by_source(source_id: int) -> None:
    """Remove all chunks for a source (used when retrying a failed indexing run)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_chunks WHERE source_id = %s", (source_id,))
        conn.commit()

def reset_aia_source_for_retry(uuid: str) -> None:
    """Resets a source to pending and clears error and OCR report."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_sources
                   SET status = 'pending', error_message = NULL, chunk_count = 0,
                       ocr_info = NULL
                   WHERE uuid = %s""",
                (uuid,),
            )
        conn.commit()


# --- KI Tutor: Chunks ---

