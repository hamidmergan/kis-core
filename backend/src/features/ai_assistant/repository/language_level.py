"""Read/write CEFR language level columns on the users table, plus the
Sprachtrainer switch that decides whether the level is applied at all.

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


LANGUAGE_TRAINING_SETTING = "language_training_enabled"


def is_language_training_enabled_globally() -> bool:
    """System-wide switch for the Sprachtrainer, set by the admin. Off by default.

    Off means the feature does not exist for anyone: no owner setting, no tiles, no
    adaptive output. The per-workspace choice stays stored while it is off, so
    switching the feature back on restores every workspace as it was.
    """
    from src.features.admin.repository.settings import get_setting

    return get_setting(LANGUAGE_TRAINING_SETTING, "false").lower() == "true"


def is_language_training_active(workspace_id: int) -> bool:
    """Whether the Sprachtrainer is on in this workspace, admin switch included.

    The owner decides this for everyone in the workspace. The CEFR level is stored
    globally per user, so this is also the gate that keeps level-pitched answers and
    tools out of workspaces that do not run the trainer.
    """
    if not is_language_training_enabled_globally():
        return False
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT language_training_active FROM aia_workspaces WHERE id = %s",
                (workspace_id,),
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
