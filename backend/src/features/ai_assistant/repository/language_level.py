"""Reads and writes the language level and the language trainer switch."""

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
    """Platform wide switch for the language trainer, off by default."""
    from src.features.admin.repository.settings import get_setting

    return get_setting(LANGUAGE_TRAINING_SETTING, "false").lower() == "true"


def is_language_training_active(workspace_id: int) -> bool:
    """Whether the language trainer is on in this course room, admin switch included."""
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
