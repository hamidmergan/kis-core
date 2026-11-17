"""Learning statistics of one person in a course room."""

from datetime import date, timedelta

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection
from src.features.ai_assistant.repository.stats_admin import (  # noqa: F401
    get_aia_admin_stats,
    get_aia_workspace_stats,
)
from src.utils.local_date import today as local_today

# Which tool belongs to which of the two areas, the exercise routes read the same list.
LANGUAGE_TRAINING_TOOLS = ("flashcards", "grammatik", "wortschatz")
LERNTOOLS_TOOLS = ("karteikarten", "quiz")

# How far the statistics reach back, calendar and cleanup depend on it.
STATS_WINDOW_DAYS = 180

# Midnight of the local day as a UTC wall time, the form the timestamp columns are stored in.
_LOCAL_MIDNIGHT_UTC = (
    "(NOW() AT TIME ZONE 'Europe/Berlin')::date::timestamp"
    " AT TIME ZONE 'Europe/Berlin' AT TIME ZONE 'UTC'"
)


def sql_tool_list(tools: tuple[str, ...]) -> str:
    """The tools as a literal IN-list. Fixed strings from this module, never user input."""
    return ", ".join(f"'{tool}'" for tool in tools)


def _summarise(subset: list[dict]) -> dict:
    """Totals over a list of sets with their attempt counts."""
    total_attempts = sum(s["total_attempts"] for s in subset)
    total_correct = sum(s["total_correct"] for s in subset)
    return {
        "total_sets": len(subset),
        "total_cards": sum(s["card_count"] for s in subset),
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "accuracy": round(total_correct / total_attempts * 100) if total_attempts > 0 else 0,
    }


def _heatmap(cur, workspace_id: int, user_id: int, today: date,
             tools: tuple[str, ...] | None = None) -> list[dict]:
    """Activity per local day over the window, days without answers are filled with zeros."""
    tool_clause = f" AND s2.tool IN ({sql_tool_list(tools)})" if tools else ""
    cur.execute(
        f"""SELECT (ep.answered_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date AS day,
                  COUNT(ep.id) AS answers,
                  COUNT(ep.id) FILTER (WHERE ep.correct) AS correct,
                  COUNT(ep.id) FILTER (WHERE NOT ep.correct) AS wrong,
                  COUNT(DISTINCT ep.set_id) AS sets_practiced
           FROM aia_exercise_progress ep
           JOIN aia_exercise_sets s2 ON s2.id = ep.set_id
           WHERE ep.user_id = %s
             AND s2.workspace_id = %s AND s2.user_id = %s
             {tool_clause}
             AND ep.answered_at >= {_LOCAL_MIDNIGHT_UTC}
                 - INTERVAL '{STATS_WINDOW_DAYS - 1} days'
           GROUP BY day ORDER BY day""",
        (user_id, workspace_id, user_id),
    )
    raw = {str(r["day"]): r for r in cur.fetchall()}
    leer = {"answers": 0, "correct": 0, "wrong": 0, "sets_practiced": 0}
    result = []
    for i in range(STATS_WINDOW_DAYS - 1, -1, -1):
        day = str(today - timedelta(days=i))
        r = raw.get(day, leer)
        result.append({
            "day": day,
            "answers": r["answers"],
            "correct": r["correct"],
            "wrong": r["wrong"],
            "sets_practiced": r["sets_practiced"],
        })
    return result


def get_student_stats(workspace_id: int, user_id: int) -> dict:
    """Aggregate personal learning stats for a student in a workspace."""
    today = local_today()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT current_streak, max_streak, last_active_date "
                "FROM aia_streaks WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            streak_row = cur.fetchone()
            streak = dict(streak_row) if streak_row else {
                "current_streak": 0, "max_streak": 0, "last_active_date": None,
            }
            if streak["last_active_date"]:
                streak["last_active_date"] = str(streak["last_active_date"])

            cur.execute(
                """SELECT s.id, s.tool, s.mode, s.title, s.card_count,
                          s.source_uuid, s.created_at,
                          COALESCE(m.total_attempts, 0) AS total_attempts,
                          COALESCE(m.total_correct, 0) AS total_correct
                   FROM aia_exercise_sets s
                   LEFT JOIN LATERAL (
                     SELECT COUNT(*) AS total_attempts,
                            COUNT(*) FILTER (WHERE p.correct) AS total_correct
                     FROM aia_exercise_progress p
                     WHERE p.set_id = s.id AND p.user_id = s.user_id
                   ) m ON true
                   WHERE s.workspace_id = %s AND s.user_id = %s AND s.status = 'ready'
                   ORDER BY s.created_at DESC""",
                (workspace_id, user_id),
            )
            sets = [dict(r) for r in cur.fetchall()]

            heatmap = _heatmap(cur, workspace_id, user_id, today)
            heatmap_lerntools = _heatmap(cur, workspace_id, user_id, today, LERNTOOLS_TOOLS)
            heatmap_language_training = _heatmap(
                cur, workspace_id, user_id, today, LANGUAGE_TRAINING_TOOLS)

            cur.execute(
                f"""SELECT COUNT(*) AS total,
                          COUNT(*) FILTER (WHERE created_at >= {_LOCAL_MIDNIGHT_UTC}) AS today
                   FROM aia_messages
                   WHERE workspace_id = %s AND user_id = %s AND role = 'user'""",
                (workspace_id, user_id),
            )
            chat_row = cur.fetchone()

            cur.execute(
                """SELECT MIN(answered_at) AS first_activity
                   FROM aia_exercise_progress ep
                   JOIN aia_exercise_sets s ON s.id = ep.set_id
                   WHERE s.workspace_id = %s AND ep.user_id = %s""",
                (workspace_id, user_id),
            )
            first_row = cur.fetchone()
            first_activity = str(first_row["first_activity"].date()) if first_row and first_row["first_activity"] else None

    return {
        "streak": streak,
        "overview": _summarise(sets),
        "lerntools": _summarise([s for s in sets if s["tool"] in LERNTOOLS_TOOLS]),
        "language_training": _summarise([s for s in sets if s["tool"] in LANGUAGE_TRAINING_TOOLS]),
        "heatmap": heatmap,
        "lerntools_heatmap": heatmap_lerntools,
        "language_training_heatmap": heatmap_language_training,
        "chat": {"total": chat_row["total"], "today": chat_row["today"]},
        "first_activity": first_activity,
        "active_days": sum(1 for d in heatmap if d["answers"] > 0),
        "today": str(today),
    }


def get_student_day_stats(workspace_id: int, user_id: int, day_str: str, category: str | None = None) -> dict:
    """Breakdown of a day, one row per round instead of a mixed rate."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            mode_clause = ""
            params: list = [workspace_id, user_id, day_str]
            if category == "language_training":
                mode_clause = f" AND s.tool IN ({sql_tool_list(LANGUAGE_TRAINING_TOOLS)})"
            elif category == "lerntools":
                mode_clause = f" AND s.tool IN ({sql_tool_list(LERNTOOLS_TOOLS)})"
            # Grouped per set and round, answers without a number form the round 'earlier'.
            cur.execute(
                f"""SELECT s.id AS set_id, s.tool, s.mode, s.title, s.card_count,
                          ep.run_no,
                          COUNT(ep.id) AS answers,
                          COUNT(ep.id) FILTER (WHERE ep.correct) AS correct,
                          COUNT(ep.id) FILTER (WHERE NOT ep.correct) AS wrong,
                          MIN(ep.answered_at) AS first_answer,
                          MAX(ep.answered_at) AS last_answer
                   FROM aia_exercise_progress ep
                   JOIN aia_exercise_sets s ON s.id = ep.set_id
                   WHERE s.workspace_id = %s AND ep.user_id = %s
                     AND (ep.answered_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date = %s::date
                     {mode_clause}
                   GROUP BY s.id, ep.run_no
                   ORDER BY MIN(ep.answered_at)""",
                params,
            )
            saetze: dict[int, dict] = {}
            total_answers = 0
            total_correct = 0
            total_wrong = 0
            for r in cur.fetchall():
                zeile = dict(r)
                satz = saetze.setdefault(zeile["set_id"], {
                    "set_id": zeile["set_id"],
                    "tool": zeile["tool"],
                    "mode": zeile["mode"],
                    "title": zeile["title"],
                    "answers": 0,
                    "correct": 0,
                    "wrong": 0,
                    "runs": [],
                })
                satz["answers"] += zeile["answers"]
                satz["correct"] += zeile["correct"]
                satz["wrong"] += zeile["wrong"]
                satz["runs"].append({
                    "run_no": zeile["run_no"],
                    "correct": zeile["correct"],
                    "total": zeile["card_count"],
                    "first_answer": zeile["first_answer"].isoformat() + "Z",
                    "last_answer": zeile["last_answer"].isoformat() + "Z",
                })
                total_answers += zeile["answers"]
                total_correct += zeile["correct"]
                total_wrong += zeile["wrong"]

            # Most recently practised set on top, rounds inside it in their order.
            sets = sorted(
                saetze.values(),
                key=lambda s: s["runs"][-1]["last_answer"],
                reverse=True,
            )

            # Chat messages that day
            cur.execute(
                """SELECT COUNT(*) AS cnt
                   FROM aia_messages
                   WHERE workspace_id = %s AND user_id = %s AND role = 'user'
                     AND (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date = %s::date""",
                (workspace_id, user_id, day_str),
            )
            chat_count = cur.fetchone()["cnt"]

    return {
        "day": day_str,
        "sets": sets,
        "total_answers": total_answers,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "chat_count": chat_count,
    }

def get_recent_activities(workspace_id: int, user_id: int, limit: int = 5) -> list[dict]:
    """Return the most recently used or created exercise sets + mindmaps for the activity feed."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM (
                     SELECT s.id AS set_id, s.tool, s.mode, s.title,
                            s.created_at,
                            MAX(ep.answered_at) AS last_answer,
                            COUNT(ep.id) AS answers,
                            COUNT(ep.id) FILTER (WHERE ep.correct) AS correct
                     FROM aia_exercise_sets s
                     LEFT JOIN aia_exercise_progress ep
                          ON ep.set_id = s.id AND ep.user_id = %s
                     WHERE s.workspace_id = %s AND s.user_id = %s
                       AND s.status = 'ready'
                     GROUP BY s.id
                   UNION ALL
                     SELECT m.id AS set_id, 'mindmap' AS tool, 'source' AS mode,
                            COALESCE(m.title, m.mindmap->>'topic', 'Mindmap') AS title,
                            m.created_at,
                            m.created_at AS last_answer,
                            0 AS answers, 0 AS correct
                     FROM aia_mindmaps m
                     WHERE m.workspace_id = %s AND m.user_id = %s AND m.status = 'success'
                   UNION ALL
                     SELECT d.id AS set_id, 'data_table' AS tool, 'source' AS mode,
                            COALESCE(d.title, 'DataTable') AS title,
                            d.created_at,
                            d.created_at AS last_answer,
                            0 AS answers, 0 AS correct
                     FROM aia_data_tables d
                     WHERE d.workspace_id = %s AND d.user_id = %s AND d.status = 'success'
                   ) combined
                   ORDER BY COALESCE(last_answer, created_at) DESC
                   LIMIT %s""",
                (user_id, workspace_id, user_id, workspace_id, user_id, workspace_id, user_id, limit),
            )
            results = []
            for r in cur.fetchall():
                row = dict(r)
                ts = row["last_answer"] or row["created_at"]
                row["last_answer"] = ts.isoformat() + "Z" if ts else None
                row.pop("created_at", None)
                results.append(row)
            return results
