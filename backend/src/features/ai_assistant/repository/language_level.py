"""Read/write CEFR language level columns on the users table, plus the
Fachsprachentrainer switch that decides whether the level is applied at all.

The diagnosis is a one-time self-assessment per user (global, not workspace-scoped).
Two columns: language_level (A1-C2 or NULL) and language_level_set_at.
"""

import psycopg2.extras

from src.core.db.pool import get_connection


def set_user_language_level(user_id: int, level: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET language_level = %s,
                    language_level_set_at = NOW()
                WHERE id = %s
                """,
                (level, user_id),
            )
        conn.commit()


def get_user_language_level(user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT language_level, language_level_set_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"language_level": None, "language_level_set_at": None}
            return {
                "language_level": row["language_level"],
                "language_level_set_at": row["language_level_set_at"],
            }


def is_language_training_active(workspace_id: int, user_id: int) -> bool:
    """Whether the learner has the Fachsprachentrainer toggled on for this workspace.

    The CEFR level is stored globally per user, so this per-workspace switch is what
    gates every adaptive appendix (chat and tools). Students who never enable it stay
    on the plain, unadapted output. Off by default (no settings row).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT language_training_active FROM aia_user_settings "
                "WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
            return bool(row[0]) if row else False


def clear_user_language_level(user_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET language_level = NULL, language_level_set_at = NULL WHERE id = %s",
                (user_id,),
            )
        conn.commit()
