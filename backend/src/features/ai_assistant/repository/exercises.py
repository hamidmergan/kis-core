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
    grammar_kinds: list[str] | None = None,
) -> dict:
    """Create a placeholder set with status='generating'. Returns the set.

    ``grammar_topic_id`` is only set by the grammar tool and points at the workspace
    topic the set was built from; it stays NULL for every other tool.

    ``source_uuids`` is the learner's whole selection, in the order they picked it. That
    order becomes the numbering of the citation chips, so it has to be stored rather than
    recomputed. ``source_uuid`` keeps holding the first one for older clients.

    ``requested_count`` is the size the learner picked. It is kept because a retry has
    to generate the same size, and card_count is 0 on a set that never finished.

    ``grammar_kinds`` sind die gewaehlten Aufgabenformate der Grammatik-Uebung. NULL
    heisst gemischt, also alle vier, und das ist der Normalfall. Ein zweiter Anlauf
    liest die Spalte wieder und uebt damit dieselbe Auswahl wie der erste.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO aia_exercise_sets
                   (workspace_id, user_id, tool, title, mode, source_uuid, card_count,
                    status, grammar_topic_id, source_uuids, requested_count,
                    grammar_kinds)
                   VALUES (%s, %s, %s, %s, %s, %s, 0, 'generating', %s, %s::jsonb, %s,
                           %s::jsonb)
                   RETURNING *""",
                (workspace_id, user_id, tool, title, mode, source_uuid, grammar_topic_id,
                 json.dumps(list(source_uuids or [])), requested_count,
                 json.dumps(grammar_kinds) if grammar_kinds else None),
            )
            ex_set = dict(cur.fetchone())
        conn.commit()
    return ex_set


def reset_exercise_set_for_retry(set_id: int, user_id: int) -> dict | None:
    """Put a failed set back into 'generating' so its task can run again.

    Returns the set with everything the generation task needs, or None when the set
    is not this user's or is not in the failed state. Scoping the UPDATE itself keeps
    a double click, or two tabs, from queueing the same set twice: the second call
    finds nothing to update.
    """
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
                # A run that died between writing its items and marking the set ready
                # leaves them behind. The second run appends, so without this the set
                # comes back with both halves in it.
                cur.execute("DELETE FROM aia_exercise_items WHERE set_id = %s", (set_id,))
        conn.commit()
    return dict(row) if row else None

def finalize_exercise_set(
    set_id: int, title: str, items: list[dict], header: dict | None = None,
) -> dict:
    """Add items to a placeholder set and mark as ready.

    ``header`` carries the grammar tool's set-level text (instruction and the worked
    example pair). It is shown once above the sentences, so it belongs on the set and
    not on every item. Other tools pass None and the columns stay NULL.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for i, item in enumerate(items):
                # Eine Aufgabe aus dem Vorrat wird nicht kopiert, der Satz zeigt nur
                # dorthin. Ihr Inhalt steht genau einmal, naemlich im Vorrat.
                # ``front`` bleibt trotzdem gefuellt, weil die Spalte NOT NULL ist und
                # weil sie die Vergleichsform fuer "hatte ich schon" traegt.
                #
                # Verschwindet der Vorrat, weil die Quelle geloescht oder neu
                # hochgeladen wird, schreibt ``materialize_pool_items`` den Inhalt
                # vorher in diese Zeilen zurueck. Ein fertiger Satz bleibt lesbar.
                aus_vorrat = bool(item.get("pool_item_id"))
                cur.execute(
                    """INSERT INTO aia_exercise_items
                       (set_id, position, front, back, back_en, options, correct_idx,
                        source_label, page_number, explanation, start_time, sources, extras,
                        pool_item_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
                    ),
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
    """List exercise sets for a user in a workspace with mastery info.

    ``progress_pct`` is what the ring on the card shows: the share of cards whose
    LAST answer was correct. Per card, not per attempt, so a card that was wrong
    and is now right counts as learned, and one that was right and is now wrong
    does not.

    It used to be the correct answers of the last run, cut off by a timestamp the
    browser set when the learner answered the first card of a session. Anything
    answered before that mark was dropped, so interrupting an exercise and coming
    back showed less than the learner had right (reported: 40 percent at 4 of 5).
    """
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
    """Titles of the most recent ready sets of this workspace+tool, newest first.

    Without them the model has no idea a set already exists and simply names the
    document, which is why several sets end up sharing one title."""
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
            # Aufgaben aus dem Vorrat stehen nur einmal, naemlich dort. Die Zeile im Satz
            # ist ein Verweis, ihre Inhaltsspalten sind leer. COALESCE holt deshalb je
            # Feld den Vorratswert, wo es einen gibt, und faellt sonst auf die Zeile
            # zurueck: alte Saetze von vor dem Vorrat und Aufgaben ohne zuordenbare
            # Quelle tragen ihren Inhalt weiter selbst.
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
    """Owner + workspace of a set, without loading its items. For authorization
    checks on the single-set routes (get/delete/progress) so one user cannot
    reach another user's set by guessing the serial id."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, workspace_id, user_id, tool FROM aia_exercise_sets WHERE id = %s",
                (set_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def delete_exercise_set(set_id: int, user_id: int) -> bool:
    """Delete an exercise set and all related data, scoped to its owner so a set
    can never be deleted by another user via its serial id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_exercise_sets WHERE id = %s AND user_id = %s RETURNING id",
                (set_id, user_id),
            )
            deleted = cur.fetchone() is not None
        conn.commit()
    return deleted

def bulk_record_exercise_progress(set_id: int, user_id: int, results: list[dict]) -> None:
    """Record multiple exercise answers at once."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for r in results:
                cur.execute(
                    """INSERT INTO aia_exercise_progress
                       (set_id, item_id, user_id, correct) VALUES (%s, %s, %s, %s)""",
                    (set_id, r["item_id"], user_id, r["correct"]),
                )
        conn.commit()


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

