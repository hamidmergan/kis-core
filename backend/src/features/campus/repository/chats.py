"""Chats and messages of the campus assistant, one person owns each chat."""
import json

import psycopg2.extras

from src.core.db.pool import get_connection

_CHAT_COLS = "id, user_id, title, question_count, created_at, updated_at"
_MSG_COLS = "id, chat_id, role, content, sources, places, no_source, feedback, created_at"


def create_chat(user_id: int, title: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO campus_chats (user_id, title) VALUES (%s, %s) RETURNING id", (user_id, title))
            chat_id = cur.fetchone()[0]
        conn.commit()
    return chat_id


def list_chats(user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT {_CHAT_COLS} FROM campus_chats WHERE user_id = %s ORDER BY updated_at DESC, id DESC", (user_id,))
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_chat(chat_id: int, user_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT {_CHAT_COLS} FROM campus_chats WHERE id = %s AND user_id = %s", (chat_id, user_id))
            row = cur.fetchone()
    return dict(row) if row else None


def rename_chat(chat_id: int, user_id: int, title: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE campus_chats SET title = %s WHERE id = %s AND user_id = %s", (title, chat_id, user_id))
            ok = cur.rowcount == 1
        conn.commit()
    return ok


def delete_chat(chat_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM campus_chats WHERE id = %s AND user_id = %s", (chat_id, user_id))
            ok = cur.rowcount == 1
        conn.commit()
    return ok


def count_question(chat_id: int) -> int:
    """Counts one more question and returns the new total."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE campus_chats SET question_count = question_count + 1, updated_at = NOW() WHERE id = %s RETURNING question_count",
                (chat_id,),
            )
            n = cur.fetchone()[0]
        conn.commit()
    return n


def drop_oldest_round(chat_id: int) -> None:
    """Removes the oldest question and its answer to make room for a new one."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM campus_messages WHERE id IN (SELECT id FROM campus_messages WHERE chat_id = %s ORDER BY id LIMIT 2)",
                (chat_id,),
            )
            cur.execute("UPDATE campus_chats SET question_count = GREATEST(question_count - 1, 0) WHERE id = %s", (chat_id,))
        conn.commit()


def touch_chat(chat_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE campus_chats SET updated_at = NOW() WHERE id = %s", (chat_id,))
        conn.commit()


def enforce_chat_cap(user_id: int, cap: int) -> int:
    """Deletes the least recently used chats beyond the cap, returns how many went."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM campus_chats WHERE id IN (
                       SELECT id FROM campus_chats WHERE user_id = %s
                       ORDER BY updated_at DESC, id DESC OFFSET %s)""",
                (user_id, cap),
            )
            n = cur.rowcount
        conn.commit()
    return n


def add_message(chat_id: int, role: str, content: str, sources: list | None = None, places: list | None = None, no_source: bool = False) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO campus_messages (chat_id, role, content, sources, places, no_source)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (chat_id, role, content, json.dumps(sources) if sources is not None else None,
                 json.dumps(places) if places is not None else None, no_source),
            )
            mid = cur.fetchone()[0]
        conn.commit()
    return mid


def list_messages(chat_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT {_MSG_COLS} FROM campus_messages WHERE chat_id = %s ORDER BY id", (chat_id,))
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def last_rounds(chat_id: int, n: int) -> list[tuple[str, str]]:
    """The last n completed rounds as (question, answer), oldest first, for making a follow-up question stand on its own."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT role, content FROM campus_messages WHERE chat_id = %s ORDER BY id DESC LIMIT %s",
                (chat_id, n * 2),
            )
            rows = list(reversed(cur.fetchall()))
    rounds: list[tuple[str, str]] = []
    pending = None
    for row in rows:
        if row["role"] == "user":
            pending = row["content"]
        elif row["role"] == "assistant" and pending is not None:
            rounds.append((pending, row["content"]))
            pending = None
    return rounds



def set_feedback(message_id: int, user_id: int, value: int) -> bool:
    """Only the owner of the chat may rate an answer."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE campus_messages m SET feedback = %s
                   FROM campus_chats c
                   WHERE m.id = %s AND m.chat_id = c.id AND c.user_id = %s AND m.role = 'assistant'""",
                (value, message_id, user_id),
            )
            ok = cur.rowcount == 1
        conn.commit()
    return ok


def prune_chats(days: int) -> int:
    """Removes chats without activity for this many days, 0 keeps everything."""
    if days <= 0:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM campus_chats WHERE updated_at < NOW() - make_interval(days => %s)", (days,))
            n = cur.rowcount
        conn.commit()
    return n


def feedback_stats() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FILTER (WHERE feedback = 1), COUNT(*) FILTER (WHERE feedback = -1),
                          COUNT(*) FILTER (WHERE role = 'assistant')
                   FROM campus_messages"""
            )
            up, down, total = cur.fetchone()
    return {"up": up, "down": down, "answers": total}
