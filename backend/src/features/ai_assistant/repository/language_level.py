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
    """Platform wide switch, off by default, it also decides whether the start question is asked."""
    from src.features.admin.repository.settings import get_setting

    return get_setting(LANGUAGE_TRAINING_SETTING, "false").lower() == "true"


def get_user_language_training(user_id: int) -> dict:
    """The person's switch and whether the start question was answered."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT language_training_active, language_training_asked_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"language_training_active": False, "language_training_asked_at": None}
    return {
        "language_training_active": bool(row["language_training_active"]),
        "language_training_asked_at": row["language_training_asked_at"],
    }


def set_user_language_training(user_id: int, active: bool) -> None:
    """Sets the switch, the first write also marks the start question as answered."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET language_training_active = %s,
                    language_training_asked_at = COALESCE(language_training_asked_at, NOW())
                WHERE id = %s
                """,
                (active, user_id),
            )
        conn.commit()


def is_language_training_offered(user_id: int) -> bool:
    """Admin switch and the person's switch, that opens the test and the profile block."""
    if not is_language_training_enabled_globally():
        return False
    return get_user_language_training(user_id)["language_training_active"]


def is_language_training_ready(user_id: int) -> bool:
    """Offered plus a stored level, that opens the tiles and the level adaptation."""
    if not is_language_training_offered(user_id):
        return False
    return bool(get_user_language_level(user_id)["language_level"])


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
