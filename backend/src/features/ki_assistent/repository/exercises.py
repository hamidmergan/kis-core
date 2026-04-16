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


def create_exercise_set(
    module_id: int, user_id: int, tool: str, title: str,
    mode: str, source_uuid: str | None, items: list[dict],
) -> dict:
    """Create an exercise set with its items. Returns the set with items."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO ki_tutor_exercise_sets
                   (module_id, user_id, tool, title, mode, source_uuid, card_count, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'ready') RETURNING *""",
                (module_id, user_id, tool, title, mode, source_uuid, len(items)),
            )
            ex_set = dict(cur.fetchone())
            created_items = []
            for i, item in enumerate(items):
                cur.execute(
                    """INSERT INTO ki_tutor_exercise_items
                       (set_id, position, front, back, back_en, options, correct_idx,
                        source_label, page_number, explanation, start_time, sources, extras)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                    (
                        ex_set["id"], i,
                        item["front"], item["back"], item.get("back_en"),
                        json.dumps(item.get("options")) if item.get("options") else None,
                        item.get("correct_idx"),
                        item.get("source_label"),
                        item.get("page_number"),
                        item.get("explanation"),
                        item.get("start_time"),
                        json.dumps(item.get("sources")) if item.get("sources") else None,
                        json.dumps(item.get("extras")) if item.get("extras") else None,
                    ),
                )
                created_items.append(dict(cur.fetchone()))
        conn.commit()
    ex_set["items"] = created_items
    return ex_set

def create_exercise_set_placeholder(
    module_id: int, user_id: int, tool: str, title: str,
    mode: str, source_uuid: str | None,
) -> dict:
    """Create a placeholder set with status='generating'. Returns the set."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO ki_tutor_exercise_sets
                   (module_id, user_id, tool, title, mode, source_uuid, card_count, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 0, 'generating') RETURNING *""",
                (module_id, user_id, tool, title, mode, source_uuid),
            )
            ex_set = dict(cur.fetchone())
        conn.commit()
    return ex_set

def finalize_exercise_set(set_id: int, title: str, items: list[dict]) -> dict:
    """Add items to a placeholder set and mark as ready."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for i, item in enumerate(items):
                cur.execute(
                    """INSERT INTO ki_tutor_exercise_items
                       (set_id, position, front, back, back_en, options, correct_idx,
                        source_label, page_number, explanation, start_time, sources, extras)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        set_id, i,
                        item["front"], item["back"], item.get("back_en"),
                        json.dumps(item.get("options")) if item.get("options") else None,
                        item.get("correct_idx"),
                        item.get("source_label"),
                        item.get("page_number"),
                        item.get("explanation"),
                        item.get("start_time"),
                        json.dumps(item.get("sources")) if item.get("sources") else None,
                        json.dumps(item.get("extras")) if item.get("extras") else None,
                    ),
                )
            cur.execute(
                """UPDATE ki_tutor_exercise_sets
                   SET status = 'ready', title = %s, card_count = %s
                   WHERE id = %s RETURNING *""",
                (title, len(items), set_id),
            )
            ex_set = dict(cur.fetchone())
        conn.commit()
    return ex_set

def fail_exercise_set(set_id: int) -> None:
    """Mark a set as failed."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ki_tutor_exercise_sets SET status = 'failed' WHERE id = %s",
                (set_id,),
            )
        conn.commit()

def get_exercise_sets(module_id: int, user_id: int, tool: str | None = None) -> list[dict]:
    """List exercise sets for a user in a module with mastery info."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where = "s.module_id = %s AND s.user_id = %s"
            params: list = [module_id, user_id]
            if tool:
                where += " AND s.tool = %s"
                params.append(tool)
            cur.execute(
                f"""SELECT s.*,
                           COALESCE(m.total_attempts, 0) AS total_attempts,
                           COALESCE(m.items_correct, 0) AS items_correct,
                           CASE WHEN s.card_count > 0
                                THEN ROUND(COALESCE(m.items_correct, 0)::numeric / s.card_count * 100)
                                ELSE 0 END AS progress_pct,
                           COALESCE(lr.last_run_correct, 0) AS last_run_correct
                    FROM ki_tutor_exercise_sets s
                    LEFT JOIN LATERAL (
                      SELECT COUNT(*) AS total_attempts,
                             COUNT(DISTINCT item_id) FILTER (WHERE correct) AS items_correct
                      FROM ki_tutor_exercise_progress p
                      WHERE p.set_id = s.id AND p.user_id = s.user_id
                    ) m ON true
                    LEFT JOIN LATERAL (
                      SELECT COUNT(DISTINCT item_id) FILTER (WHERE correct) AS last_run_correct
                      FROM ki_tutor_exercise_progress p
                      WHERE p.set_id = s.id AND p.user_id = s.user_id
                        AND s.last_run_start IS NOT NULL
                        AND p.answered_at >= s.last_run_start
                    ) lr ON true
                    WHERE {where}
                    ORDER BY s.created_at DESC""",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

def get_existing_exercise_fronts(
    module_id: int, tool: str, limit: int = 150,
) -> list[str]:
    """Return the `front` text of recent exercise items for this module+tool.
    Used to give the LLM awareness of what already exists so it can create variations."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT i.front
                   FROM ki_tutor_exercise_items i
                   JOIN ki_tutor_exercise_sets s ON i.set_id = s.id
                   WHERE s.module_id = %s AND s.tool = %s AND s.status = 'ready'
                   ORDER BY s.created_at DESC, i.position ASC
                   LIMIT %s""",
                (module_id, tool, limit),
            )
            return [row[0] for row in cur.fetchall() if row[0]]

def get_exercise_set_with_items(set_id: int) -> dict | None:
    """Get a single set with all its items, enriching with chunk start_time where missing."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_exercise_sets WHERE id = %s", (set_id,))
            ex_set = cur.fetchone()
            if not ex_set:
                return None
            ex_set = dict(ex_set)
            cur.execute(
                "SELECT * FROM ki_tutor_exercise_items WHERE set_id = %s ORDER BY position",
                (set_id,),
            )
            items = [dict(r) for r in cur.fetchall()]

            # Enrich items (top-level AND nested sources[]) with start_time where missing.
            # Legacy sets may only have page_number; download/UI needs timestamp for media.
            def _needs_top(it: dict) -> bool:
                return bool(it.get("page_number")) and it.get("start_time") is None and bool(it.get("source_label"))

            def _needs_nested(it: dict) -> list[dict]:
                return [
                    s for s in (it.get("sources") or [])
                    if s.get("page_number") and s.get("start_time") is None and s.get("source_label")
                ]

            any_needs = any(_needs_top(it) or _needs_nested(it) for it in items)
            if any_needs:
                module_id = ex_set["module_id"]
                cur.execute("SELECT id, filename FROM ki_tutor_sources WHERE module_id = %s", (module_id,))
                src_map = {r["filename"]: r["id"] for r in cur.fetchall()}
                source_ids = list(src_map.values())
                if source_ids:
                    cur.execute(
                        "SELECT source_id, page_number, start_time FROM ki_tutor_chunks "
                        "WHERE source_id = ANY(%s) AND start_time IS NOT NULL",
                        (source_ids,),
                    )
                    time_map = {(r["source_id"], r["page_number"]): r["start_time"] for r in cur.fetchall()}
                    for it in items:
                        if _needs_top(it):
                            sid = src_map.get(it["source_label"])
                            st = time_map.get((sid, it["page_number"])) if sid else None
                            if st is not None:
                                it["start_time"] = st
                        for s in _needs_nested(it):
                            sid = src_map.get(s["source_label"])
                            st = time_map.get((sid, s["page_number"])) if sid else None
                            if st is not None:
                                s["start_time"] = st

            ex_set["items"] = items
            return ex_set

def delete_exercise_set(set_id: int) -> bool:
    """Delete an exercise set and all related data."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_exercise_sets WHERE id = %s RETURNING id", (set_id,))
            deleted = cur.fetchone() is not None
        conn.commit()
    return deleted

def record_exercise_progress(set_id: int, item_id: int, user_id: int, correct: bool) -> None:
    """Record a single exercise answer."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_exercise_progress
                   (set_id, item_id, user_id, correct) VALUES (%s, %s, %s, %s)""",
                (set_id, item_id, user_id, correct),
            )
        conn.commit()

def start_new_run(set_id: int) -> None:
    """Mark the start of a new exercise run."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ki_tutor_exercise_sets SET last_run_start = NOW() WHERE id = %s",
                (set_id,),
            )
        conn.commit()

def bulk_record_exercise_progress(set_id: int, user_id: int, results: list[dict]) -> None:
    """Record multiple exercise answers at once."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for r in results:
                cur.execute(
                    """INSERT INTO ki_tutor_exercise_progress
                       (set_id, item_id, user_id, correct) VALUES (%s, %s, %s, %s)""",
                    (set_id, r["item_id"], user_id, r["correct"]),
                )
        conn.commit()


# ─── Streak Tracking ──────────────────────────────────────────────────────────

def update_streak(module_id: int, user_id: int) -> dict:
    """Update streak for today (Berlin timezone). Returns current and max streak."""
    from datetime import timedelta, datetime
    today = datetime.now(_TZ_BERLIN).date()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM ki_tutor_streaks WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    """INSERT INTO ki_tutor_streaks
                       (module_id, user_id, current_streak, max_streak, last_active_date)
                       VALUES (%s, %s, 1, 1, %s) RETURNING *""",
                    (module_id, user_id, today),
                )
                result = dict(cur.fetchone())
            else:
                row = dict(row)
                last = row["last_active_date"]
                if last == today:
                    result = row
                elif last == today - timedelta(days=1):
                    new_streak = row["current_streak"] + 1
                    new_max = max(row["max_streak"], new_streak)
                    cur.execute(
                        """UPDATE ki_tutor_streaks
                           SET current_streak = %s, max_streak = %s, last_active_date = %s
                           WHERE id = %s RETURNING *""",
                        (new_streak, new_max, today, row["id"]),
                    )
                    result = dict(cur.fetchone())
                else:
                    cur.execute(
                        """UPDATE ki_tutor_streaks
                           SET current_streak = 1, last_active_date = %s
                           WHERE id = %s RETURNING *""",
                        (today, row["id"]),
                    )
                    result = dict(cur.fetchone())
        conn.commit()
    return result

def get_streak(module_id: int, user_id: int) -> dict:
    """Get current streak info."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM ki_tutor_streaks WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return {"current_streak": 0, "max_streak": 0, "last_active_date": None}
            return dict(row)

def get_glossary_count(module_id: int) -> int:
    """Get total glossary entry count for a module."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM ki_tutor_glossary_entries g
                   JOIN ki_tutor_sources s ON s.id = g.source_id
                   WHERE s.module_id = %s""",
                (module_id,),
            )
            return cur.fetchone()[0]

