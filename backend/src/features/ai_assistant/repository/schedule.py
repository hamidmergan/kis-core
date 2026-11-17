"""Schedule entries, private appointments and calendar colours, the generation side lives in schedule_jobs."""

import json
from datetime import date, datetime, time
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection
from src.features.ai_assistant.repository.schedule_jobs import (  # noqa: F401
    clear_source_extractions,
    clear_workspace_source_extractions,
    count_source_extractions,
    create_schedule_job,
    get_active_schedule_job,
    get_processed_source_ids,
    get_schedule_job,
    get_source_extraction,
    mark_source_processed,
    update_schedule_job,
    upsert_source_extraction,
)


_ENTRY_COLS = (
    "id, workspace_id, type, title, description, due_date, end_date, "
    "due_time, end_time, date_precision, is_open_ended, "
    "is_optional, is_checked, checked_at, origin, "
    "source_refs, year_assumed, created_at, updated_at"
)


def _assign(sets: list[str], params: list, column: str, value, clear: bool = False) -> None:
    """Adds one column to a partial update, clear writes NULL, None leaves it alone."""
    if clear:
        sets.append(f"{column} = NULL")
    elif value is not None:
        sets.append(f"{column} = %s")
        params.append(value)


def _assign_checked(sets: list[str], params: list, is_checked: Optional[bool]) -> None:
    """Ticks or unticks an entry, the time of the tick is stored in UTC like every timestamp."""
    if is_checked is not None:
        sets.append("is_checked = %s")
        params.append(is_checked)
        sets.append("checked_at = %s")
        params.append(datetime.utcnow() if is_checked else None)


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
    """Collects appointments across all course rooms the person has a relation to."""
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
               s.due_date, s.end_date, s.due_time, s.end_time,
               s.date_precision, s.is_open_ended,
               s.is_optional, s.is_checked, s.checked_at, s.origin,
               s.source_refs, s.year_assumed, s.created_at, s.updated_at,
               m.uuid AS workspace_uuid,
               m.title AS module_title,
               CASE WHEN s.workspace_id IS NULL THEN 'personal'
                    WHEN m.user_id = %(uid)s THEN 'owned'
                    ELSE 'enrolled' END AS module_relation
          FROM aia_schedule_entries s
          LEFT JOIN aia_workspaces m ON m.id = s.workspace_id
         WHERE s.user_id = %(uid)s
           AND (
                 s.workspace_id IS NULL
                 OR s.workspace_id IN (
                      SELECT id FROM aia_workspaces WHERE user_id = %(uid)s
                      UNION
                      SELECT m2.id
                        FROM aia_workspaces m2
                        JOIN aia_enrollments e ON e.workspace_id = m2.id
                       WHERE e.user_id = %(uid)s
                         AND m2.is_active = TRUE
                         AND (e.enrolled_until IS NULL OR e.enrolled_until > NOW())
                    )
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


def get_schedule_entries(workspace_id: int, user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_ENTRY_COLS}
                  FROM aia_schedule_entries
                 WHERE workspace_id = %s AND user_id = %s
                 ORDER BY due_date NULLS LAST, due_time NULLS LAST, id
                """,
                (workspace_id, user_id),
            )
            return [dict(r) for r in cur.fetchall()]


def get_schedule_entries_for_workspace(workspace_id: int) -> list[dict]:
    """All appointments of a course room as anchor titles against duplicate entries."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_ENTRY_COLS}, user_id
                  FROM aia_schedule_entries
                 WHERE workspace_id = %s
                 ORDER BY due_date NULLS LAST, due_time NULLS LAST, id
                """,
                (workspace_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_schedule_entry(entry_id: int, user_id: int) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {_ENTRY_COLS}, user_id
                  FROM aia_schedule_entries
                 WHERE id = %s AND user_id = %s
                """,
                (entry_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_schedule_entry(
    workspace_id: int,
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
    date_precision: str = "day",
    end_date: Optional[date] = None,
    end_time: Optional[time] = None,
    is_open_ended: bool = False,
    year_assumed: bool = False,
) -> dict:
    """Creates an appointment, date_precision 'month' sets the first of the month as sort key."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                INSERT INTO aia_schedule_entries
                    (workspace_id, user_id, type, title, description,
                     due_date, end_date, due_time, end_time, date_precision,
                     is_open_ended, is_optional, origin, source_refs, year_assumed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {_ENTRY_COLS}
                """,
                (
                    workspace_id, user_id, type, title, description,
                    due_date, end_date, due_time, end_time,
                    date_precision if date_precision in ("day", "month") else "day",
                    is_open_ended, is_optional, origin,
                    json.dumps(source_refs), year_assumed,
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
    end_date: Optional[date] = None,
    end_time: Optional[time] = None,
    date_precision: Optional[str] = None,
    is_open_ended: Optional[bool] = None,
    is_optional: Optional[bool] = None,
    is_checked: Optional[bool] = None,
    source_refs: Optional[list[dict]] = None,
    clear_date: bool = False,
    clear_time: bool = False,
    clear_end_date: bool = False,
    clear_end_time: bool = False,
    year_confirmed: bool = False,
) -> Optional[dict]:
    """Partial update. Pass only fields to change."""
    sets: list[str] = []
    params: list[Any] = []

    _assign(sets, params, "type", type)
    _assign(sets, params, "title", title)
    _assign(sets, params, "description", description)
    _assign(sets, params, "due_date", due_date, clear_date)
    _assign(sets, params, "due_time", due_time, clear_time)
    _assign(sets, params, "end_date", end_date, clear_end_date)
    _assign(sets, params, "end_time", end_time, clear_end_time)
    if date_precision in ("day", "month"):
        _assign(sets, params, "date_precision", date_precision)
    _assign(sets, params, "is_open_ended", is_open_ended)
    _assign(sets, params, "is_optional", is_optional)
    _assign_checked(sets, params, is_checked)
    if source_refs is not None:
        sets.append("source_refs = %s")
        params.append(json.dumps(source_refs))
    if year_confirmed:
        sets.append("year_assumed = FALSE")

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


def append_source_ref_to_entry(entry_id: int, ref: dict, year_written: bool = False) -> None:
    """Attaches a source reference without duplicates, a written year ends the assumption."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE aia_schedule_entries
                   SET source_refs = (
                     SELECT COALESCE(jsonb_agg(DISTINCT x), '[]'::jsonb)
                       FROM jsonb_array_elements(source_refs || %s::jsonb) AS x
                   ),
                       year_assumed = year_assumed AND NOT %s,
                       updated_at = NOW()
                 WHERE id = %s
                """,
                (json.dumps([ref]), year_written, entry_id),
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


def remove_source_from_schedule(workspace_id: int, source_uuid: str) -> tuple[int, int]:
    """Takes a deleted source off every entry, entries it alone found go with it."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH betroffen AS (
                    SELECT id, origin, COALESCE(
                             (SELECT jsonb_agg(x) FROM jsonb_array_elements(source_refs) AS x
                               WHERE x->>'source_uuid' IS DISTINCT FROM %(uuid)s),
                             '[]'::jsonb) AS rest
                      FROM aia_schedule_entries
                     WHERE workspace_id = %(ws)s
                       AND source_refs @> %(treffer)s::jsonb
                ), weg AS (
                    DELETE FROM aia_schedule_entries s
                     USING betroffen b
                     WHERE s.id = b.id AND b.origin = 'llm' AND b.rest = '[]'::jsonb
                    RETURNING s.id
                ), rest AS (
                    UPDATE aia_schedule_entries s
                       SET source_refs = b.rest, updated_at = NOW()
                      FROM betroffen b
                     WHERE s.id = b.id AND NOT (b.origin = 'llm' AND b.rest = '[]'::jsonb)
                    RETURNING s.id
                )
                SELECT (SELECT COUNT(*) FROM weg), (SELECT COUNT(*) FROM rest)
                """,
                {"uuid": source_uuid, "ws": workspace_id,
                 "treffer": json.dumps([{"source_uuid": source_uuid}])},
            )
            geloescht, gekuerzt = cur.fetchone()
        conn.commit()
    return geloescht, gekuerzt


def delete_all_schedule_entries(workspace_id: int, user_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_schedule_entries WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            count = cur.rowcount
            cur.execute(
                "DELETE FROM aia_schedule_processed_sources WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
        conn.commit()
        return count


# ─── Eigene Termine ─────────────────────────────────────────────────────────

def create_personal_entry(
    user_id: int,
    *,
    title: str,
    description: Optional[str],
    due_date: date,
    end_date: Optional[date],
    due_time: Optional[time],
) -> dict:
    """An appointment without a workspace, it belongs to this user alone."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                INSERT INTO aia_schedule_entries
                    (workspace_id, user_id, type, title, description,
                     due_date, end_date, due_time, date_precision, is_optional,
                     origin, source_refs)
                VALUES (NULL, %s, 'termin', %s, %s, %s, %s, %s, 'day', FALSE,
                        'manual', '[]'::jsonb)
                RETURNING {_ENTRY_COLS}
                """,
                (user_id, title, description, due_date, end_date, due_time),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


def update_personal_entry(
    entry_id: int,
    user_id: int,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[date] = None,
    end_date: Optional[date] = None,
    due_time: Optional[time] = None,
    is_checked: Optional[bool] = None,
    clear_end_date: bool = False,
    clear_time: bool = False,
) -> Optional[dict]:
    """Changes a private entry, other people's and workspace entries stay untouched."""
    sets: list[str] = []
    vals: list[Any] = []
    _assign(sets, vals, "title", title)
    _assign(sets, vals, "description", description)
    _assign(sets, vals, "due_date", due_date)
    _assign(sets, vals, "end_date", end_date, clear_end_date)
    _assign(sets, vals, "due_time", due_time, clear_time)
    _assign_checked(sets, vals, is_checked)
    if not sets:
        return get_schedule_entry(entry_id, user_id)
    sets.append("updated_at = NOW()")
    vals.extend([entry_id, user_id])
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                UPDATE aia_schedule_entries SET {", ".join(sets)}
                 WHERE id = %s AND user_id = %s AND workspace_id IS NULL
                RETURNING {_ENTRY_COLS}
                """,
                vals,
            )
            conn.commit()
            row = cur.fetchone()
            return dict(row) if row else None


def delete_personal_entry(entry_id: int, user_id: int) -> bool:
    """Deletes a private entry, workspace entries stay untouched."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_schedule_entries "
                " WHERE id = %s AND user_id = %s AND workspace_id IS NULL",
                (entry_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0


# ─── Calendar colours ───────────────────────────────────────────────────────

def get_calendar_colors(user_id: int) -> dict[str, int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT group_key, color FROM aia_calendar_colors WHERE user_id = %s", (user_id,))
            return {r[0]: r[1] for r in cur.fetchall()}


def set_calendar_colors(user_id: int, colors: dict[str, int], overwrite: bool = True) -> None:
    """Without overwrite a parallel request that came first keeps its choice."""
    if not colors:
        return
    konflikt = "DO UPDATE SET color = EXCLUDED.color" if overwrite else "DO NOTHING"
    with get_connection() as conn:
        with conn.cursor() as cur:
            for key, color in colors.items():
                cur.execute(
                    f"""INSERT INTO aia_calendar_colors (user_id, group_key, color)
                        VALUES (%s, %s, %s) ON CONFLICT (user_id, group_key) {konflikt}""",
                    (user_id, key, color),
                )
        conn.commit()
