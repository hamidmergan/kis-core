import json
import os
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def create_exercise_set(
    workspace_id: int, user_id: int, tool: str, title: str,
    mode: str, source_uuid: str | None, items: list[dict],
) -> dict:
    """Create an exercise set with its items. Returns the set with items."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO aia_exercise_sets
                   (workspace_id, user_id, tool, title, mode, source_uuid, card_count, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'ready') RETURNING *""",
                (workspace_id, user_id, tool, title, mode, source_uuid, len(items)),
            )
            ex_set = dict(cur.fetchone())
            created_items = []
            for i, item in enumerate(items):
                cur.execute(
                    """INSERT INTO aia_exercise_items
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
    workspace_id: int, user_id: int, tool: str, title: str,
    mode: str, source_uuid: str | None, grammar_topic_id: int | None = None,
    source_uuids: list[str] | None = None, requested_count: int | None = None,
    flashcard_set_id: int | None = None, grammar_kinds: list[str] | None = None,
    user_instruction: str | None = None,
) -> dict:
    """Creates a placeholder set with status 'generating' and returns it."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO aia_exercise_sets
                   (workspace_id, user_id, tool, title, mode, source_uuid, card_count,
                    status, grammar_topic_id, source_uuids, requested_count,
                    flashcard_set_id, grammar_kinds, user_instruction)
                   VALUES (%s, %s, %s, %s, %s, %s, 0, 'generating', %s, %s::jsonb, %s,
                           %s, %s::jsonb, %s)
                   RETURNING *""",
                (workspace_id, user_id, tool, title, mode, source_uuid, grammar_topic_id,
                 json.dumps(list(source_uuids or [])), requested_count, flashcard_set_id,
                 json.dumps(grammar_kinds) if grammar_kinds else None,
                 user_instruction or None),
            )
            ex_set = dict(cur.fetchone())
        conn.commit()
    return ex_set


def reset_exercise_set_for_retry(set_id: int, user_id: int) -> dict | None:
    """Resets a failed set to 'generating', safe against double clicks."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """UPDATE aia_exercise_sets
                   SET status = 'generating', card_count = 0,
                       instruction = NULL, pattern_front = NULL, pattern_back = NULL
                   WHERE id = %s AND user_id = %s AND status = 'failed'
                   RETURNING *""",
                (set_id, user_id),
            )
            row = cur.fetchone()
            if row:
                # Clear leftovers of a crashed run, otherwise the set appears twice.
                cur.execute("DELETE FROM aia_exercise_items WHERE set_id = %s", (set_id,))
        conn.commit()
    return dict(row) if row else None

def finalize_exercise_set(
    set_id: int, title: str, items: list[dict], header: dict | None = None,
    user_id: int | None = None,
) -> dict:
    """Attaches exercises to the placeholder set and marks it done."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for i, item in enumerate(items):
                # The set points at the pool, front stays filled as a comparison form.
                aus_vorrat = bool(item.get("pool_item_id"))
                cur.execute(
                    """INSERT INTO aia_exercise_items
                       (set_id, position, front, back, back_en, options, correct_idx,
                        source_label, page_number, explanation, start_time, sources, extras,
                        pool_item_id, glossary_term)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        set_id, i,
                        item["front"],
                        "" if aus_vorrat else item["back"],
                        None if aus_vorrat else item.get("back_en"),
                        None if aus_vorrat or not item.get("options")
                        else json.dumps(item.get("options")),
                        None if aus_vorrat else item.get("correct_idx"),
                        None if aus_vorrat else item.get("source_label"),
                        None if aus_vorrat else item.get("page_number"),
                        None if aus_vorrat else item.get("explanation"),
                        None if aus_vorrat else item.get("start_time"),
                        None if aus_vorrat or not item.get("sources")
                        else json.dumps(item.get("sources")),
                        None if aus_vorrat or not item.get("extras")
                        else json.dumps(item.get("extras")),
                        item.get("pool_item_id"),
                        # Glossary terms never come from the pool and are therefore not cleared.
                        item.get("glossary_term"),
                    ),
                )
                # A permanent record, so a later deleted set cannot free the exercise up again.
                if aus_vorrat and user_id:
                    cur.execute(
                        """INSERT INTO aia_exercise_pool_seen (pool_item_id, user_id)
                           VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                        (item.get("pool_item_id"), user_id),
                    )
            head = header or {}
            cur.execute(
                """UPDATE aia_exercise_sets
                   SET status = 'ready', title = %s, card_count = %s,
                       instruction = COALESCE(%s, instruction),
                       pattern_front = COALESCE(%s, pattern_front),
                       pattern_back = COALESCE(%s, pattern_back)
                   WHERE id = %s RETURNING *""",
                (
                    title, len(items),
                    head.get("instruction"), head.get("pattern_front"), head.get("pattern_back"),
                    set_id,
                ),
            )
            ex_set = dict(cur.fetchone())
        conn.commit()
    return ex_set

def fail_exercise_set(set_id: int) -> None:
    """Mark a set as failed."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_exercise_sets SET status = 'failed' WHERE id = %s",
                (set_id,),
            )
        conn.commit()

def get_exercise_sets(workspace_id: int, user_id: int, tool: str | None = None) -> list[dict]:
    """Lists the exercise sets with progress, counted per card instead of per attempt."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where = "s.workspace_id = %s AND s.user_id = %s"
            params: list = [workspace_id, user_id]
            if tool:
                where += " AND s.tool = %s"
                params.append(tool)
            cur.execute(
                f"""SELECT s.*,
                           COALESCE(m.total_attempts, 0) AS total_attempts,
                           COALESCE(m.items_correct, 0) AS items_correct,
                           CASE WHEN s.card_count > 0
                                THEN LEAST(100, ROUND(
                                       COALESCE(m.items_correct, 0)::numeric
                                       / s.card_count * 100))
                                ELSE 0 END AS progress_pct
                    FROM aia_exercise_sets s
                    LEFT JOIN LATERAL (
                      SELECT
                        (SELECT COUNT(*) FROM aia_exercise_progress p
                          WHERE p.set_id = s.id AND p.user_id = s.user_id
                        ) AS total_attempts,
                        (SELECT COUNT(*) FROM (
                           SELECT DISTINCT ON (p.item_id) p.correct
                           FROM aia_exercise_progress p
                           WHERE p.set_id = s.id AND p.user_id = s.user_id
                           ORDER BY p.item_id, p.answered_at DESC, p.id DESC
                         ) letzte WHERE letzte.correct
                        ) AS items_correct
                    ) m ON true
                    WHERE {where}
                    ORDER BY s.created_at DESC""",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

def get_recent_exercise_titles(
    workspace_id: int, tool: str, limit: int = 12,
) -> list[str]:
    """Titles of the last finished sets so the model does not reuse names."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT title FROM aia_exercise_sets
                   WHERE workspace_id = %s AND tool = %s AND status = 'ready'
                     AND title IS NOT NULL AND title <> ''
                   ORDER BY created_at DESC
                   LIMIT %s""",
                (workspace_id, tool, limit),
            )
            return [row[0] for row in cur.fetchall() if row[0]]

def get_exercise_set_with_items(set_id: int) -> dict | None:
    """Get a single set with all its items, enriching with chunk start_time where missing."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM aia_exercise_sets WHERE id = %s", (set_id,))
            ex_set = cur.fetchone()
            if not ex_set:
                return None
            ex_set = dict(ex_set)
            # COALESCE takes the pool value per field and falls back to the row.
            cur.execute(
                """SELECT i.id, i.set_id, i.position, i.pool_item_id,
                          COALESCE(p.front, i.front)               AS front,
                          COALESCE(p.back, i.back)                 AS back,
                          COALESCE(p.back_en, i.back_en)           AS back_en,
                          COALESCE(p.options, i.options)           AS options,
                          COALESCE(p.correct_idx, i.correct_idx)   AS correct_idx,
                          COALESCE(p.explanation, i.explanation)   AS explanation,
                          COALESCE(p.source_label, i.source_label) AS source_label,
                          COALESCE(p.page_number, i.page_number)   AS page_number,
                          COALESCE(p.start_time, i.start_time)     AS start_time,
                          COALESCE(p.sources, i.sources)           AS sources,
                          COALESCE(p.extras, i.extras)             AS extras
                   FROM aia_exercise_items i
                   LEFT JOIN aia_exercise_pool p ON p.id = i.pool_item_id
                   WHERE i.set_id = %s ORDER BY i.position""",
                (set_id,),
            )
            items = [dict(r) for r in cur.fetchall()]

            # Backfill missing timestamps, old sets only have page numbers.
            def _needs_top(it: dict) -> bool:
                return bool(it.get("page_number")) and it.get("start_time") is None and bool(it.get("source_label"))

            def _needs_nested(it: dict) -> list[dict]:
                return [
                    s for s in (it.get("sources") or [])
                    if s.get("page_number") and s.get("start_time") is None and s.get("source_label")
                ]

            any_needs = any(_needs_top(it) or _needs_nested(it) for it in items)
            if any_needs:
                workspace_id = ex_set["workspace_id"]
                cur.execute("SELECT id, filename FROM aia_sources WHERE workspace_id = %s", (workspace_id,))
                src_map = {r["filename"]: r["id"] for r in cur.fetchall()}
                source_ids = list(src_map.values())
                if source_ids:
                    cur.execute(
                        "SELECT source_id, page_number, start_time FROM aia_chunks "
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

def get_exercise_set_meta(set_id: int) -> dict | None:
    """Owner and course room of a set, for the permission check without loading exercises."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, workspace_id, user_id, tool FROM aia_exercise_sets WHERE id = %s",
                (set_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def delete_exercise_set(set_id: int, user_id: int) -> bool:
    """Deletes an exercise set with everything, scoped to its owner."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_exercise_sets WHERE id = %s AND user_id = %s RETURNING id",
                (set_id, user_id),
            )
            deleted = cur.fetchone() is not None
        conn.commit()
    return deleted

def bulk_record_exercise_progress(
    set_id: int, user_id: int, results: list[dict], new_run: bool = False,
) -> None:
    """Writes several answers at once, this function assigns the round number."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(run_no), 0) FROM aia_exercise_progress "
                "WHERE set_id = %s AND user_id = %s",
                (set_id, user_id),
            )
            hoechste = cur.fetchone()[0]
            # The one catches the case where the very first answer never arrived.
            run_no = hoechste + 1 if new_run else max(hoechste, 1)
            for r in results:
                # A card answered again in the same round is a correction, not a
                # second answer, so the old verdict goes before the new one lands.
                cur.execute(
                    "DELETE FROM aia_exercise_progress "
                    "WHERE set_id = %s AND item_id = %s AND user_id = %s AND run_no = %s",
                    (set_id, r["item_id"], user_id, run_no),
                )
                cur.execute(
                    """INSERT INTO aia_exercise_progress
                       (set_id, item_id, user_id, correct, run_no)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (set_id, r["item_id"], user_id, r["correct"], run_no),
                )
        conn.commit()


def seed_exercise_progress(rows: list[dict]) -> None:
    """Backdated answers for the demo tour's default stats, real practice never needs this.

    Each row: set_id, item_id, user_id, correct, run_no, answered_at.
    """
    if not rows:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    """INSERT INTO aia_exercise_progress
                       (set_id, item_id, user_id, correct, run_no, answered_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (r["set_id"], r["item_id"], r["user_id"], r["correct"],
                     r["run_no"], r["answered_at"]),
                )
        conn.commit()


def hat_heute_geuebt(workspace_id: int, user_id: int) -> bool:
    """Whether this person has any exercise answer today (Berlin time) in this workspace."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM aia_exercise_progress ep
                   JOIN aia_exercise_sets s ON s.id = ep.set_id
                   WHERE s.workspace_id = %s AND ep.user_id = %s
                     AND (ep.answered_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date
                       = (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date
                   LIMIT 1""",
                (workspace_id, user_id),
            )
            return cur.fetchone() is not None


def prune_old_exercise_progress() -> int:
    """Clears answers older than the calendar view reaches."""
    from src.features.ai_assistant.repository.stats import STATS_WINDOW_DAYS

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""DELETE FROM aia_exercise_progress alt
                    WHERE alt.answered_at < NOW() - INTERVAL '{STATS_WINDOW_DAYS} days'
                      AND EXISTS (
                        SELECT 1 FROM aia_exercise_progress neuer
                        WHERE neuer.set_id = alt.set_id
                          AND neuer.user_id = alt.user_id
                          AND neuer.item_id = alt.item_id
                          AND (neuer.answered_at, neuer.id) > (alt.answered_at, alt.id)
                      )"""
            )
            entfernt = cur.rowcount
        conn.commit()
    return entfernt


# ─── Streak Tracking ──────────────────────────────────────────────────────────

def update_streak(workspace_id: int, user_id: int) -> dict:
    """Update streak for today (Berlin timezone). Returns current and max streak."""
    from datetime import timedelta, datetime
    today = datetime.now(_TZ_BERLIN).date()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM aia_streaks WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    """INSERT INTO aia_streaks
                       (workspace_id, user_id, current_streak, max_streak, last_active_date)
                       VALUES (%s, %s, 1, 1, %s) RETURNING *""",
                    (workspace_id, user_id, today),
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
                        """UPDATE aia_streaks
                           SET current_streak = %s, max_streak = %s, last_active_date = %s
                           WHERE id = %s RETURNING *""",
                        (new_streak, new_max, today, row["id"]),
                    )
                    result = dict(cur.fetchone())
                else:
                    cur.execute(
                        """UPDATE aia_streaks
                           SET current_streak = 1, last_active_date = %s
                           WHERE id = %s RETURNING *""",
                        (today, row["id"]),
                    )
                    result = dict(cur.fetchone())
        conn.commit()
    return result

def get_streak(workspace_id: int, user_id: int) -> dict:
    """Get current streak info."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM aia_streaks WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return {"current_streak": 0, "max_streak": 0, "last_active_date": None}
            return dict(row)


def seed_streak(workspace_id: int, user_id: int, current_streak: int, last_active_date) -> None:
    """Sets a starting streak for the demo tour, only when there is none yet."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_streaks (workspace_id, user_id, current_streak, max_streak, last_active_date)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (workspace_id, user_id) DO NOTHING""",
                (workspace_id, user_id, current_streak, current_streak, last_active_date),
            )
        conn.commit()

def get_glossary_count(workspace_id: int, user_id: int) -> int:
    """Get the user's glossary entry count for a workspace."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM aia_glossary_entries g
                   JOIN aia_sources s ON s.id = g.source_id
                   WHERE s.workspace_id = %s AND g.user_id = %s""",
                (workspace_id, user_id),
            )
            return cur.fetchone()[0]

