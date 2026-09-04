"""Reads and writes the language level and the language trainer switch."""

import psycopg2.extras

from src.core.db.pool import get_connection


def set_user_language_level(user_id: int, level: str, source: str = "test") -> None:
    """Stores the level and switches the trainer on, source says who set it."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET language_level = %s,
                    language_level_set_at = NOW(),
                    language_level_source = %s
                WHERE id = %s
                """,
                (level, source, user_id),
            )
        conn.commit()
    # A stored level is the clearest yes, that also opens the tiles in the module.
    set_user_language_training(user_id, True)


def get_user_language_level(user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT language_level, language_level_set_at, language_level_source "
                "FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"language_level": None, "language_level_set_at": None,
                        "language_level_source": None}
            return {
                "language_level": row["language_level"],
                "language_level_set_at": row["language_level_set_at"],
                "language_level_source": row["language_level_source"],
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


def may_use_language_training(user_id: int) -> bool:
    """The permission alone, roles without it never see the trainer."""
    from src.dependencies_rbac import permissions_of
    from src.features.admin.repository.users import get_user_by_id
    from src.permissions_registry import PERM_AIA_LANGUAGE_LEVEL

    row = get_user_by_id(user_id)
    if not row:
        return False
    return permissions_of(dict(row)).has(PERM_AIA_LANGUAGE_LEVEL)


def is_language_training_offered(user_id: int) -> bool:
    """Admin switch and the permission, that opens the level page and the test."""
    if not is_language_training_enabled_globally():
        return False
    return may_use_language_training(user_id)


def is_language_training_ready(user_id: int) -> bool:
    """Offered plus a stored level, that opens the tiles and the level adaptation."""
    if not is_language_training_offered(user_id):
        return False
    return bool(get_user_language_level(user_id)["language_level"])


def clear_user_language_level(user_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET language_level = NULL, language_level_set_at = NULL, "
                "language_level_source = NULL WHERE id = %s",
                (user_id,),
            )
        conn.commit()
