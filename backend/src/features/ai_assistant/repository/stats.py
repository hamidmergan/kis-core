import os
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection

# Which tool belongs to which of the two areas, the exercise routes read the same list.
LANGUAGE_TRAINING_TOOLS = ("flashcards", "grammatik", "wortschatz")
LERNTOOLS_TOOLS = ("karteikarten", "quiz")

# How far the statistics reach back, calendar and cleanup depend on it.
STATS_WINDOW_DAYS = 180


def sql_tool_list(tools: tuple[str, ...]) -> str:
    """The tools as a literal IN-list. Fixed strings from this module, never user input."""
    return ", ".join(f"'{tool}'" for tool in tools)


def get_student_stats(workspace_id: int, user_id: int) -> dict:
    """Aggregate personal learning stats for a student in a workspace."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Berlin")

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ── Streak ──
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

            # ── All exercise sets ──
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

            # ── Split by category: Lerntools (mode=source) vs LanguageTraining (mode=glossary) ──
            def _summarise(subset: list[dict]) -> dict:
                total_cards = sum(s["card_count"] for s in subset)
                total_attempts = sum(s["total_attempts"] for s in subset)
                total_correct = sum(s["total_correct"] for s in subset)
                return {
                    "total_sets": len(subset),
                    "total_cards": total_cards,
                    "total_attempts": total_attempts,
                    "total_correct": total_correct,
                    "accuracy": round(total_correct / total_attempts * 100) if total_attempts > 0 else 0,
                }

            lerntools_sets = [s for s in sets if s["tool"] in LERNTOOLS_TOOLS]
            lang_sets = [s for s in sets if s["tool"] in LANGUAGE_TRAINING_TOOLS]

            overview_all = _summarise(sets)
            overview_lerntools = _summarise(lerntools_sets)
            overview_language_training = _summarise(lang_sets)

            # (by_tool removed - not displayed anymore)

            # ── Heatmap: activity per day per category (last 6 months, Berlin tz) ──
            from datetime import timedelta, datetime
            today = datetime.now(tz).date()

            def _build_heatmap(category_filter: str | None) -> list[dict]:
                mode_clause = ""
                params: list = [user_id, workspace_id, user_id]
                if category_filter == "language_training":
                    mode_clause = f" AND s2.tool IN ({sql_tool_list(LANGUAGE_TRAINING_TOOLS)})"
                elif category_filter == "lerntools":
                    mode_clause = f" AND s2.tool IN ({sql_tool_list(LERNTOOLS_TOOLS)})"
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
                         {mode_clause}
                         AND ep.answered_at >= (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date
                             - INTERVAL '{STATS_WINDOW_DAYS - 1} days'
                       GROUP BY day ORDER BY day""",
                    params,
                )
                raw = {str(r["day"]): dict(r) for r in cur.fetchall()}
                result = []
                for i in range(STATS_WINDOW_DAYS - 1, -1, -1):
                    d = today - timedelta(days=i)
                    ds = str(d)
                    if ds in raw:
                        r = raw[ds]
                        result.append({
                            "day": ds,
                            "answers": r["answers"],
                            "correct": r["correct"],
                            "wrong": r["wrong"],
                            "sets_practiced": r["sets_practiced"],
                        })
                    else:
                        result.append({
                            "day": ds, "answers": 0, "correct": 0,
                            "wrong": 0, "sets_practiced": 0,
                        })
                return result

            heatmap = _build_heatmap(None)
            heatmap_lerntools = _build_heatmap("lerntools")
            heatmap_language_training = _build_heatmap("language_training")

            # ── Chat stats ──
            cur.execute(
                """SELECT COUNT(*) AS total,
                          COUNT(*) FILTER (
                            WHERE created_at >= (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date
                          ) AS today
                   FROM aia_messages
                   WHERE workspace_id = %s AND user_id = %s AND role = 'user'""",
                (workspace_id, user_id),
            )
            chat_row = cur.fetchone()

            # ── First activity date ──
            cur.execute(
                """SELECT MIN(answered_at) AS first_activity
                   FROM aia_exercise_progress ep
                   JOIN aia_exercise_sets s ON s.id = ep.set_id
                   WHERE s.workspace_id = %s AND ep.user_id = %s""",
                (workspace_id, user_id),
            )
            first_row = cur.fetchone()
            first_activity = str(first_row["first_activity"].date()) if first_row and first_row["first_activity"] else None

            # ── Total active days ──
            active_days = sum(1 for d in heatmap if d["answers"] > 0)

    return {
        "streak": streak,
        "overview": overview_all,
        "lerntools": overview_lerntools,
        "language_training": overview_language_training,
        "heatmap": heatmap,
        "lerntools_heatmap": heatmap_lerntools,
        "language_training_heatmap": heatmap_language_training,
        "chat": {"total": chat_row["total"], "today": chat_row["today"]},
        "first_activity": first_activity,
        "active_days": active_days,
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
                            COALESCE(m.mindmap->>'topic', 'Mindmap') AS title,
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


# ─── Admin: KI-Tutor Statistics ──────────────────────────────────────────────

def get_aia_admin_stats(days: int = 30, mode: str | None = None) -> dict:
    """Numbers of the AI tutor for the admin area."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            interval = f"{days} days"

            # Mode filter for exercise queries (requires JOIN with aia_exercise_sets as s)
            mode_filter = ""
            mode_params: tuple = ()
            if mode in ("source", "glossary"):
                mode_filter = " AND s.mode = %s"
                mode_params = (mode,)

            # ── 1. Summary ──
            cur.execute("SELECT COUNT(*) AS cnt FROM aia_workspaces WHERE NOT is_podcast_store")
            total_workspaces = cur.fetchone()["cnt"]

            cur.execute(
                f"""SELECT COUNT(DISTINCT p.user_id) AS cnt
                    FROM aia_exercise_progress p
                    JOIN aia_exercise_sets s ON s.id = p.set_id
                    WHERE p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                (interval, *mode_params),
            )
            active_students = cur.fetchone()["cnt"]

            cur.execute(
                f"""SELECT COUNT(*) AS cnt
                    FROM aia_exercise_progress p
                    JOIN aia_exercise_sets s ON s.id = p.set_id
                    WHERE p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                (interval, *mode_params),
            )
            total_answers = cur.fetchone()["cnt"]

            cur.execute(
                """SELECT COUNT(*) AS cnt FROM aia_messages
                   WHERE role = 'user' AND created_at >= NOW() - INTERVAL %s""",
                (interval,),
            )
            total_chat_messages = cur.fetchone()["cnt"]

            # ── 2. Workspace list with lecturer activity + enrolled students ──
            cur.execute(
                """SELECT m.id, m.uuid, m.title, m.is_active, m.user_id AS owner_id,
                          u.display_name AS owner_name, u.ldap_username AS owner_username,
                          (SELECT COUNT(*) FROM aia_enrollments e WHERE e.workspace_id = m.id) AS enrollment_count,
                          (SELECT COUNT(DISTINCT src.id) FROM aia_sources src WHERE src.workspace_id = m.id) AS source_count
                   FROM aia_workspaces m
                   JOIN users u ON m.user_id = u.id
                   WHERE NOT m.is_podcast_store
                   ORDER BY m.created_at DESC""",
            )
            workspaces_raw = [dict(r) for r in cur.fetchall()]

            workspace_stats = []
            for m in workspaces_raw:
                mid = m["id"]
                owner_id = m["owner_id"]
                owner = m["owner_name"] or m["owner_username"] or "Unbekannt"

                # Lecturer activity: chat messages sent by owner in this workspace
                cur.execute(
                    """SELECT COUNT(*) AS cnt FROM aia_messages
                       WHERE workspace_id = %s AND user_id = %s AND role = 'user'
                         AND created_at >= NOW() - INTERVAL %s""",
                    (mid, owner_id, interval),
                )
                lecturer_messages = cur.fetchone()["cnt"]

                # Lecturer activity: exercises answered by owner
                cur.execute(
                    f"""SELECT COUNT(p.id) AS attempts,
                               COUNT(p.id) FILTER (WHERE p.correct) AS correct_cnt
                        FROM aia_exercise_progress p
                        JOIN aia_exercise_sets s ON s.id = p.set_id
                        WHERE s.workspace_id = %s AND p.user_id = %s
                          AND p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                    (mid, owner_id, interval, *mode_params),
                )
                lecturer_ex = cur.fetchone()

                # Total workspace exercise stats
                cur.execute(
                    f"""SELECT COUNT(p.id) AS total_answers,
                               COUNT(p.id) FILTER (WHERE p.correct) AS total_correct
                        FROM aia_exercise_progress p
                        JOIN aia_exercise_sets s ON s.id = p.set_id
                        WHERE s.workspace_id = %s AND p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                    (mid, interval, *mode_params),
                )
                ex_row = cur.fetchone()

                # Total chat in workspace
                cur.execute(
                    """SELECT COUNT(*) AS cnt FROM aia_messages
                       WHERE workspace_id = %s AND role = 'user'
                         AND created_at >= NOW() - INTERVAL %s""",
                    (mid, interval),
                )
                chat_cnt = cur.fetchone()["cnt"]

                # Enrolled students with their individual stats
                cur.execute(
                    """SELECT DISTINCT u.id AS user_id,
                              u.display_name, u.ldap_username
                       FROM aia_enrollments e
                       JOIN users u ON e.user_id = u.id
                       WHERE e.workspace_id = %s
                       ORDER BY u.display_name""",
                    (mid,),
                )
                enrolled = [dict(r) for r in cur.fetchall()]

                students = []
                for st in enrolled:
                    sid = st["user_id"]
                    # Student exercises in this workspace
                    cur.execute(
                        f"""SELECT COUNT(p.id) AS answers,
                                   COUNT(p.id) FILTER (WHERE p.correct) AS correct_cnt,
                                   COUNT(p.id) FILTER (WHERE s.mode = 'source') AS lerntools,
                                   COUNT(p.id) FILTER (WHERE s.mode = 'glossary') AS language_training
                            FROM aia_exercise_progress p
                            JOIN aia_exercise_sets s ON s.id = p.set_id
                            WHERE s.workspace_id = %s AND p.user_id = %s
                              AND p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                        (mid, sid, interval, *mode_params),
                    )
                    st_ex = cur.fetchone()

                    # Student chat messages in this workspace
                    cur.execute(
                        """SELECT COUNT(*) AS cnt FROM aia_messages
                           WHERE workspace_id = %s AND user_id = %s AND role = 'user'
                             AND created_at >= NOW() - INTERVAL %s""",
                        (mid, sid, interval),
                    )
                    st_chat = cur.fetchone()["cnt"]

                    students.append({
                        "name": st["display_name"] or st["ldap_username"] or "Unbekannt",
                        "answers": st_ex["answers"],
                        "correct": st_ex["correct_cnt"],
                        "accuracy": round(st_ex["correct_cnt"] / st_ex["answers"] * 100) if st_ex["answers"] > 0 else 0,
                        "lerntools": st_ex["lerntools"],
                        "language_training": st_ex["language_training"],
                        "chat_messages": st_chat,
                    })

                workspace_stats.append({
                    "workspace_uuid": m["uuid"],
                    "title": m["title"],
                    "owner": owner,
                    "is_active": m["is_active"],
                    "source_count": m["source_count"],
                    "enrollment_count": m["enrollment_count"],
                    "total_answers": ex_row["total_answers"],
                    "accuracy": round(ex_row["total_correct"] / ex_row["total_answers"] * 100) if ex_row["total_answers"] > 0 else 0,
                    "chat_messages": chat_cnt,
                    "lecturer": {
                        "messages": lecturer_messages,
                        "exercises": lecturer_ex["attempts"],
                    },
                    "students": students,
                })

    return {
        "summary": {
            "total_workspaces": total_workspaces,
            "active_students": active_students,
            "total_answers": total_answers,
            "total_chat_messages": total_chat_messages,
        },
        "workspace_stats": workspace_stats,
        "days": days,
        "mode": mode,
    }


# ─── Lecturer: Module Statistics ──────────────────────────────────────────────

def get_aia_workspace_stats(workspace_id: int) -> dict:
    """Statistics for a single workspace - used by the workspace owner (Lecturer)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT user_id) AS cnt FROM aia_enrollments WHERE workspace_id = %s",
                (workspace_id,),
            )
            total_enrolled = cur.fetchone()["cnt"]

            cur.execute(
                """SELECT COUNT(DISTINCT user_id) AS cnt
                   FROM aia_messages
                   WHERE workspace_id = %s AND role = 'user'
                     AND created_at >= NOW() - INTERVAL '30 days'""",
                (workspace_id,),
            )
            active_30d = cur.fetchone()["cnt"]

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM aia_messages WHERE workspace_id = %s AND role = 'user'",
                (workspace_id,),
            )
            total_chat = cur.fetchone()["cnt"]

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM aia_exercise_sets WHERE workspace_id = %s",
                (workspace_id,),
            )
            total_sets = cur.fetchone()["cnt"]

    return {
        "overview": {
            "total_enrolled": total_enrolled,
            "active_30d": active_30d,
            "total_chat_messages": total_chat,
            "total_exercise_sets": total_sets,
        },
    }

