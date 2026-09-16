"""Conversations of the interpreter and their sentences in the database."""

import uuid
from datetime import datetime

import psycopg2.extras

from src.core.db.pool import get_connection
from src.limits import MAX_INTERPRETER_SESSIONS

SESSION_FIELDS = ("left_lang", "right_lang", "left_name", "right_name", "ended_at")


def create_session(owner_id: int, left_lang: str, right_lang: str, left_name: str, right_name: str) -> dict:
    """The new conversation is written, then the owner is trimmed back to the pool."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """INSERT INTO interpreter_sessions (id, owner_id, left_lang, right_lang, left_name, right_name)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (uuid.uuid4().hex, owner_id, left_lang, right_lang, left_name, right_name),
            )
            row = dict(cur.fetchone())
            _evict_oldest(cur, owner_id)
        conn.commit()
        return row


def _evict_oldest(cur, owner_id: int, cap: int = MAX_INTERPRETER_SESSIONS) -> int:
    """Everything past the newest cap conversations goes, sentences follow by cascade."""
    cur.execute(
        """DELETE FROM interpreter_sessions
            WHERE owner_id = %s
              AND id NOT IN (SELECT id FROM interpreter_sessions
                             WHERE owner_id = %s ORDER BY updated_at DESC LIMIT %s)""",
        (owner_id, owner_id, cap),
    )
    return cur.rowcount


def get_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM interpreter_sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def list_sessions(owner_id: int, limit: int = MAX_INTERPRETER_SESSIONS) -> list[dict]:
    """The owner's conversations, newest first, with the first sentence and the count."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT s.*,
                          (SELECT COUNT(*) FROM interpreter_turns t WHERE t.session_id = s.id) AS turn_count,
                          (SELECT t.original FROM interpreter_turns t WHERE t.session_id = s.id
                             ORDER BY t.at ASC, t.created_at ASC LIMIT 1) AS first_original,
                          (SELECT t.side FROM interpreter_turns t WHERE t.session_id = s.id
                             ORDER BY t.at ASC, t.created_at ASC LIMIT 1) AS first_side,
                          (SELECT t.translation FROM interpreter_turns t WHERE t.session_id = s.id
                             ORDER BY t.at ASC, t.created_at ASC LIMIT 1) AS first_translation
                   FROM interpreter_sessions s
                   WHERE s.owner_id = %s
                   ORDER BY s.updated_at DESC
                   LIMIT %s""",
                (owner_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]


def update_session(session_id: str, **fields) -> dict | None:
    unknown = set(fields) - set(SESSION_FIELDS)
    if unknown:
        raise ValueError(f"unknown session fields: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = %s" for name in fields)
    values = list(fields.values())
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""UPDATE interpreter_sessions
                    SET {assignments + ', ' if assignments else ''}updated_at = NOW()
                    WHERE id = %s
                    RETURNING *""",
                (*values, session_id),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def delete_session(session_id: str, owner_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM interpreter_sessions WHERE id = %s AND owner_id = %s", (session_id, owner_id))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted


def upsert_turn(session_id: str, turn: dict) -> dict:
    """Writes a sentence as a whole, a repeated write replaces text, translation and status."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("UPDATE interpreter_sessions SET updated_at = NOW() WHERE id = %s", (session_id,))
            cur.execute(
                """INSERT INTO interpreter_turns
                       (id, session_id, side, source, original, translation, status, edited, at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                       original = EXCLUDED.original,
                       translation = EXCLUDED.translation,
                       status = EXCLUDED.status,
                       edited = EXCLUDED.edited,
                       updated_at = NOW()
                   RETURNING *""",
                (
                    turn["id"], session_id, turn["side"], turn["source"], turn["original"],
                    turn["translation"], turn["status"], turn["edited"], turn["at"],
                ),
            )
            row = dict(cur.fetchone())
        conn.commit()
        return row


def delete_turn(session_id: str, turn_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM interpreter_turns WHERE id = %s AND session_id = %s", (turn_id, session_id))
        conn.commit()


def list_turns(session_id: str) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM interpreter_turns WHERE session_id = %s ORDER BY at ASC, created_at ASC",
                (session_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def now() -> datetime:
    return datetime.now()
