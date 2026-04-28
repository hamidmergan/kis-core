"""KI-Assistent repository — schedule entries + processed sources."""

import json
from datetime import date, datetime, time
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection


_ENTRY_COLS = (
    "id, type, title, description, due_date, due_time, "
    "is_optional, is_checked, checked_at, origin, "
    "source_refs, created_at, updated_at"
)


# ─── Entries ────────────────────────────────────────────────────────────────

def get_schedule_entries_for_user(
    user_id: int,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
    include_checked: bool = False,
    only_checked: bool = False,
    include_past_open: bool = False,
) -> list[dict]:
    """Aggregate schedule entries across all modules the user has any relation to.

    Module scope: UNION of
      - modules owned by the user (any is_active state), and
      - modules the user is enrolled in (is_active=TRUE AND enrollment not expired).
    A user who is both owner and enrolled sees the module once (UNION dedupes).

    Returns rows enriched with module_uuid, module_title, module_relation
    (owned | enrolled).

    Filter modes (priority: only_checked > include_past_open > default):
      - default: future unchecked (due_date >= today AND is_checked=FALSE)
      - include_checked=True: also include checked entries
      - include_past_open=True: drop the date filter (missed deadlines visible)
      - only_checked=True: completed entries only, no date filter (history view)
    include_past_open + include_checked together → no filter at all (full view).
    """
    if only_checked:
        status_filter = "AND s.is_checked = TRUE"
    elif include_past_open:
        status_filter = "" if include_checked else "AND s.is_checked = FALSE"
    else:
        date_filter = "AND s.due_date >= (NOW() AT TIME ZONE 'Europe/Berlin')::date"
        checked_filter = "" if include_checked else "AND s.is_checked = FALSE"
        status_filter = f"{date_filter} {checked_filter}"

    sql = f"""
        SELECT s.id, s.type, s.title, s.description,
               s.due_date, s.due_time,
               s.is_optional, s.is_checked, s.checked_at, s.origin,
               s.source_refs, s.created_at, s.updated_at,
               m.uuid AS module_uuid,
               m.title AS module_title,
               CASE WHEN m.user_id = %(uid)s THEN 'owned' ELSE 'enrolled' END
                   AS module_relation
          FROM aia_schedule_entries s
          JOIN aia_modules m ON m.id = s.module_id
         WHERE s.module_id IN (
                 SELECT id FROM aia_modules WHERE user_id = %(uid)s
                 UNION
                 SELECT m2.id
                   FROM aia_modules m2
                   JOIN aia_enrollments e ON e.module_id = m2.id
                  WHERE e.user_id = %(uid)s
                    AND m2.is_active = TRUE
                    AND (e.enrolled_until IS NULL OR e.enrolled_until > NOW())
               )
           AND s.due_date IS NOT NULL
           {status_filter}
         ORDER BY s.due_date ASC, s.due_time NULLS LAST, s.id
    """
    params: dict[str, Any] = {"uid": user_id}
    if limit is not None:
        sql += " LIMIT %(limit)s"
        params["limit"] = int(limit)
    if offset > 0:
        sql += " OFFSET %(offset)s"
        params["offset"] = int(offset)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def get_schedule_entries(module_id: int, user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_ENTRY_COLS}
                  FROM aia_schedule_entries
                 WHERE module_id = %s AND user_id = %s
                 ORDER BY due_date NULLS LAST, due_time NULLS LAST, id
                """,
                (module_id, user_id),
            )
            return [dict(r) for r in cur.fetchall()]


def get_schedule_entry(entry_id: int, user_id: int) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_ENTRY_COLS}, module_id, user_id
                  FROM aia_schedule_entries
                 WHERE id = %s AND user_id = %s
                """,
                (entry_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_schedule_entry(
    module_id: int,
    user_id: int,
    *,
    type: str,
    title: str,
    description: Optional[str],
    due_date: Optional[date],
    due_time: Optional[time],
    is_optional: bool,
    origin: str,
    source_refs: list[dict],
) -> dict:
    """Create a schedule entry. source_refs is a list of
    {source_uuid, page_number?, start_time?, raw_quote?} dicts.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                INSERT INTO aia_schedule_entries
                    (module_id, user_id, type, title, description,
                     due_date, due_time, is_optional, origin, source_refs)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {_ENTRY_COLS}
                """,
                (
                    module_id, user_id, type, title, description,
                    due_date, due_time, is_optional, origin,
                    json.dumps(source_refs),
                ),
            )
            row = dict(cur.fetchone())
        conn.commit()
        return row


def update_schedule_entry(
    entry_id: int,
    user_id: int,
    *,
    type: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[date] = None,
    due_time: Optional[time] = None,
    is_optional: Optional[bool] = None,
    is_checked: Optional[bool] = None,
    source_refs: Optional[list[dict]] = None,
    clear_date: bool = False,
    clear_time: bool = False,
) -> Optional[dict]:
    """Partial update. Pass only fields to change."""
    sets: list[str] = []
    params: list[Any] = []

    if type is not None:
        sets.append("type = %s")
        params.append(type)
    if title is not None:
        sets.append("title = %s")
        params.append(title)
    if description is not None:
        sets.append("description = %s")
        params.append(description)
    if clear_date:
        sets.append("due_date = NULL")
    elif due_date is not None:
        sets.append("due_date = %s")
        params.append(due_date)
    if clear_time:
        sets.append("due_time = NULL")
    elif due_time is not None:
        sets.append("due_time = %s")
        params.append(due_time)
    if is_optional is not None:
        sets.append("is_optional = %s")
        params.append(is_optional)
    if is_checked is not None:
        sets.append("is_checked = %s")
        params.append(is_checked)
        sets.append("checked_at = %s")
        params.append(datetime.utcnow() if is_checked else None)
    if source_refs is not None:
        sets.append("source_refs = %s")
        params.append(json.dumps(source_refs))

    if not sets:
        return get_schedule_entry(entry_id, user_id)

    sets.append("updated_at = NOW()")
    sql = (
        "UPDATE aia_schedule_entries SET "
        + ", ".join(sets)
        + " WHERE id = %s AND user_id = %s "
        + f"RETURNING {_ENTRY_COLS}"
    )
    params.extend([entry_id, user_id])

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def append_source_ref_to_entry(entry_id: int, ref: dict) -> None:
    """Append a source-ref dict to an entry's source_refs JSONB array.
    Deduplicates by (source_uuid, page_number, start_time) triple.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE aia_schedule_entries
                   SET source_refs = (
                     SELECT COALESCE(jsonb_agg(DISTINCT x), '[]'::jsonb)
                       FROM jsonb_array_elements(source_refs || %s::jsonb) AS x
                   ),
                       updated_at = NOW()
                 WHERE id = %s
                """,
                (json.dumps([ref]), entry_id),
            )
        conn.commit()


def delete_schedule_entry(entry_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_schedule_entries WHERE id = %s AND user_id = %s",
                (entry_id, user_id),
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def delete_all_schedule_entries(module_id: int, user_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_schedule_entries WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            count = cur.rowcount
            cur.execute(
                "DELETE FROM aia_schedule_processed_sources WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
        conn.commit()
        return count


def prune_old_entries(months: int = 1) -> int:
    """System-wide cleanup: delete schedule entries (checked or not) whose
    due_date is older than N months. Future entries are never touched, even
    if they are already checked. Idempotent — safe to call repeatedly.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_schedule_entries "
                "WHERE due_date IS NOT NULL "
                "  AND due_date < (NOW() AT TIME ZONE 'Europe/Berlin')::date "
                "                 - (%s || ' months')::interval",
                (str(months),),
            )
            count = cur.rowcount
        conn.commit()
        return count


# ─── Processed sources ──────────────────────────────────────────────────────

def get_processed_source_ids(module_id: int, user_id: int) -> list[int]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT source_id
                  FROM aia_schedule_processed_sources
                 WHERE module_id = %s AND user_id = %s
                """,
                (module_id, user_id),
            )
            return [r["source_id"] for r in cur.fetchall()]


def mark_source_processed(module_id: int, user_id: int, source_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO aia_schedule_processed_sources (module_id, user_id, source_id)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (module_id, user_id, source_id),
            )
        conn.commit()


# ─── Generation Jobs ────────────────────────────────────────────────────────

def create_schedule_job(module_id: int, user_id: int, source_uuids: list[str]) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO aia_schedule_jobs (module_id, user_id, source_uuids, status)
                VALUES (%s, %s, %s, 'pending')
                RETURNING id, module_id, user_id, source_uuids, status, error, added_count,
                          created_at, updated_at
                """,
                (module_id, user_id, json.dumps(source_uuids)),
            )
            row = dict(cur.fetchone())
        conn.commit()
        return row


def get_active_schedule_job(module_id: int, user_id: int) -> Optional[dict]:
    """Return the newest pending/running schedule job for this module+user, if any."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, module_id, user_id, source_uuids, status, error, added_count,
                       created_at, updated_at
                  FROM aia_schedule_jobs
                 WHERE module_id = %s AND user_id = %s
                   AND status IN ('pending', 'running')
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (module_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_schedule_job(job_id: int, user_id: int) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, module_id, user_id, source_uuids, status, error, added_count,
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
