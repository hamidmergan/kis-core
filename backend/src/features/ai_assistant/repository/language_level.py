"""Read/write CEFR language level columns on the users table.

The diagnosis is a one-time self-assessment per user (global, not workspace-scoped).
Three columns: language_level (A1-C2 or NULL), language_level_set_at, language_level_skill_scores (JSONB).
"""

import json

import psycopg2.extras

from src.core.db.pool import get_connection


def set_user_language_level(user_id: int, level: str, skill_scores: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET language_level = %s,
                    language_level_set_at = NOW(),
                    language_level_skill_scores = %s::jsonb
                WHERE id = %s
                """,
                (level, json.dumps(skill_scores), user_id),
            )
        conn.commit()


def get_user_language_level(user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT language_level, language_level_set_at, language_level_skill_scores FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"language_level": None, "language_level_set_at": None, "language_level_skill_scores": None}
            return {
                "language_level": row["language_level"],
                "language_level_set_at": row["language_level_set_at"],
                "language_level_skill_scores": row["language_level_skill_scores"],
            }


def clear_user_language_level(user_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET language_level = NULL, language_level_set_at = NULL, language_level_skill_scores = NULL WHERE id = %s",
                (user_id,),
            )
        conn.commit()
