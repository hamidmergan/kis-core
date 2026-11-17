"""Schedule generation: processed sources, generation jobs and the stored source analyses."""

import json
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection


# ─── Processed sources ──────────────────────────────────────────────────────

def get_processed_source_ids(workspace_id: int, user_id: int) -> list[int]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT source_id
                  FROM aia_schedule_processed_sources
                 WHERE workspace_id = %s AND user_id = %s
                """,
                (workspace_id, user_id),
            )
            return [r["source_id"] for r in cur.fetchall()]


def mark_source_processed(workspace_id: int, user_id: int, source_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO aia_schedule_processed_sources (workspace_id, user_id, source_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (workspace_id, user_id, source_id),
            )
        conn.commit()


# ─── Generation Jobs ────────────────────────────────────────────────────────

def create_schedule_job(workspace_id: int, user_id: int, source_uuids: list[str]) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO aia_schedule_jobs (workspace_id, user_id, source_uuids, status)
                VALUES (%s, %s, %s, 'pending')
                RETURNING id, workspace_id, user_id, source_uuids, status, error, added_count,
                          created_at, updated_at
                """,
                (workspace_id, user_id, json.dumps(source_uuids)),
            )
            row = dict(cur.fetchone())
        conn.commit()
        return row


def get_active_schedule_job(workspace_id: int, user_id: int) -> Optional[dict]:
    """Return the newest pending/running schedule job for this workspace+user, if any."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, workspace_id, user_id, source_uuids, status, error, added_count,
                       created_at, updated_at
                  FROM aia_schedule_jobs
                 WHERE workspace_id = %s AND user_id = %s
                   AND status IN ('pending', 'running')
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (workspace_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_schedule_job(job_id: int, user_id: int) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, workspace_id, user_id, source_uuids, status, error, added_count,
                       created_at, updated_at
                  FROM aia_schedule_jobs
                 WHERE id = %s AND user_id = %s
                """,
                (job_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_schedule_job(
    job_id: int,
    status: str,
    *,
    error: Optional[str] = None,
    added_count: Optional[int] = None,
) -> None:
    sets = ["status = %s", "updated_at = NOW()"]
    params: list[Any] = [status]
    if error is not None:
        sets.append("error = %s")
        params.append(error)
    if added_count is not None:
        sets.append("added_count = %s")
        params.append(added_count)
    params.append(job_id)
    sql = "UPDATE aia_schedule_jobs SET " + ", ".join(sets) + " WHERE id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


# ─── Source Extractions (workspace-shared) ──────────────────────────────────

def get_source_extraction(source_id: int) -> Optional[dict]:
    """The stored analysis of a source, or None."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT candidates, classifications, extracted_at
                  FROM aia_schedule_source_extractions
                 WHERE source_id = %s
                """,
                (source_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_source_extraction(
    source_id: int,
    candidates: list[dict],
    classifications: list[dict],
) -> None:
    """Stores the analysis of a source, repeatable without error."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO aia_schedule_source_extractions
                       (source_id, candidates, classifications)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_id) DO NOTHING
                """,
                (source_id, json.dumps(candidates), json.dumps(classifications)),
            )
        conn.commit()


def clear_workspace_source_extractions(workspace_id: int) -> int:
    """Throws away the stored analyses of one course room's sources."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM aia_schedule_source_extractions
                 WHERE source_id IN (SELECT id FROM aia_sources WHERE workspace_id = %s)
                """,
                (workspace_id,),
            )
            geloescht = cur.rowcount
        conn.commit()
    return geloescht


def count_source_extractions() -> int:
    """How many sources have a stored analysis, across all course rooms."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM aia_schedule_source_extractions")
            return cur.fetchone()[0]


def clear_source_extractions() -> int:
    """Throws away the stored analyses, the marker stays."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_schedule_source_extractions")
            geloescht = cur.rowcount
        conn.commit()
    return geloescht
