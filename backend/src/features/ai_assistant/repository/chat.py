import json
import os
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
# This many messages are read to find the last usable round.
_LAST_ROUND_SCAN = 8
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def save_aia_message(
    workspace_id: int,
    user_id: int,
    role: str,
    content: str,
    source_pages: list | dict | None = None,
    enrollment_id: int | None = None,
    source_qmap: list | None = None,
    aborted: bool = False,
    failed: bool = False,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_messages
                   (workspace_id, user_id, role, content, source_pages, enrollment_id, source_qmap, aborted, failed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    workspace_id,
                    user_id,
                    role,
                    content,
                    json.dumps(source_pages) if source_pages is not None else None,
                    enrollment_id,
                    json.dumps(source_qmap) if source_qmap is not None else None,
                    aborted,
                    failed,
                ),
            )
        conn.commit()

def delete_aia_messages(workspace_id: int, user_id: int, enrollment_id: int | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if enrollment_id is not None:
                cur.execute(
                    "DELETE FROM aia_messages WHERE workspace_id = %s AND user_id = %s AND enrollment_id = %s",
                    (workspace_id, user_id, enrollment_id),
                )
            else:
                cur.execute(
                    "DELETE FROM aia_messages WHERE workspace_id = %s AND user_id = %s AND enrollment_id IS NULL",
                    (workspace_id, user_id),
                )
        conn.commit()

def get_aia_messages(
    workspace_id: int,
    user_id: int,
    limit: int = 20,
    enrollment_id: int | None = None,
    include_aborted: bool = True,
) -> list[dict]:
    """Loads the chat history, include_aborted=False leaves cancelled answers out."""
    aborted_filter = "" if include_aborted else " AND aborted = FALSE"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if enrollment_id is not None:
                cur.execute(
                    f"""SELECT * FROM aia_messages
                       WHERE workspace_id = %s AND user_id = %s AND enrollment_id = %s{aborted_filter}
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (workspace_id, user_id, enrollment_id, limit),
                )
            else:
                cur.execute(
                    f"""SELECT * FROM aia_messages
                       WHERE workspace_id = %s AND user_id = %s AND enrollment_id IS NULL{aborted_filter}
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (workspace_id, user_id, limit),
                )
            rows = cur.fetchall()
    return list(reversed([dict(row) for row in rows]))

def get_last_aia_user_questions(
    workspace_id: int, user_id: int, enrollment_id: int | None = None, limit: int = 10
) -> list[str]:
    """This person's last questions, purely as a language anchor for the next answer."""
    where = "enrollment_id = %s" if enrollment_id is not None else "enrollment_id IS NULL"
    params: tuple = (workspace_id, user_id) + (
        (enrollment_id,) if enrollment_id is not None else ()) + (limit,)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT content FROM aia_messages
                   WHERE workspace_id = %s AND user_id = %s AND role = 'user'
                     AND {where}
                   ORDER BY created_at DESC
                   LIMIT %s""",
                params,
            )
            rows = cur.fetchall()
    return [q for q in ((row["content"] or "").strip() for row in rows) if q]

def get_last_aia_rounds(
    workspace_id: int, user_id: int, enrollment_id: int | None = None, n: int = 1
) -> list[dict]:
    """The last n completed rounds, oldest first, only to make a follow-up question self-contained."""
    where = "enrollment_id = %s" if enrollment_id is not None else "enrollment_id IS NULL"
    params: tuple = (workspace_id, user_id) + (
        (enrollment_id,) if enrollment_id is not None else ()) + (max(_LAST_ROUND_SCAN, n * 4),)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT role, content, source_pages, source_qmap, aborted, failed
                   FROM aia_messages
                   WHERE workspace_id = %s AND user_id = %s
                     AND {where}
                   ORDER BY created_at DESC
                   LIMIT %s""",
                params,
            )
            rows = cur.fetchall()
    rounds: list[dict] = []
    i = 0
    while i < len(rows) and len(rounds) < n:
        row = rows[i]
        if row["role"] != "assistant" or row["aborted"] or row["failed"] or not (row["content"] or "").strip():
            i += 1
            continue
        j = next((k for k in range(i + 1, len(rows)) if rows[k]["role"] == "user"), None)
        rounds.append({
            "question": ((rows[j]["content"] if j is not None else "") or "").strip(),
            "answer": row["content"].strip(),
            "source_pages": row["source_pages"] or [],
            "source_qmap": row["source_qmap"] or [],
        })
        i = (j + 1) if j is not None else len(rows)
    return list(reversed(rounds))


def get_last_aia_round(
    workspace_id: int, user_id: int, enrollment_id: int | None = None
) -> dict | None:
    """The last completed round."""
    rounds = get_last_aia_rounds(workspace_id, user_id, enrollment_id, 1)
    return rounds[0] if rounds else None


def get_aia_user_settings(workspace_id: int, user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM aia_user_settings WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
    if row:
        return dict(row)
    return {
        "chat_lang": "de",
        "studio_enabled": True,
        "popup_translate_lang": "en",
    }

def upsert_aia_user_settings(
    workspace_id: int, user_id: int, chat_lang: str, studio_enabled: bool,
    popup_translate_lang: str = "en",
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_user_settings (workspace_id, user_id, chat_lang, studio_enabled, popup_translate_lang)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (workspace_id, user_id)
                   DO UPDATE SET chat_lang = EXCLUDED.chat_lang,
                                 studio_enabled = EXCLUDED.studio_enabled,
                                 popup_translate_lang = EXCLUDED.popup_translate_lang""",
                (workspace_id, user_id, chat_lang, studio_enabled, popup_translate_lang),
            )
        conn.commit()


# --- KI Tutor: Notes ---

