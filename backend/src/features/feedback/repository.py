"""The feedback entries in the database, without any link to who sent them
unless the sender opted in to attach their name."""
import psycopg2.extras

from src import storage
from src.core.db.pool import get_connection


def create_feedback(
    *,
    category: str,
    message: str,
    contact: str | None,
    username: str | None,
    page_path: str | None,
) -> int:
    """Stores one entry and returns its id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO feedback (category, message, contact, username, page_path)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id""",
                (category, message, contact, username, page_path),
            )
            feedback_id = cur.fetchone()[0]
        conn.commit()
        return feedback_id


def add_attachment(
    *,
    feedback_id: int,
    filename: str,
    content_type: str,
    size_bytes: int,
    storage_key: str,
) -> int:
    """Registers one stored attachment against its feedback entry."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO feedback_attachments
                       (feedback_id, filename, content_type, size_bytes, storage_key)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id""",
                (feedback_id, filename, content_type, size_bytes, storage_key),
            )
            attachment_id = cur.fetchone()[0]
        conn.commit()
        return attachment_id


def get_attachment(attachment_id: int) -> dict | None:
    """One attachment, for serving it back."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM feedback_attachments WHERE id = %s", (attachment_id,))
            zeile = cur.fetchone()
            return dict(zeile) if zeile else None


def list_feedback() -> list[dict]:
    """All entries with their attachments, newest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM feedback ORDER BY created_at DESC")
            rows = [dict(zeile) for zeile in cur.fetchall()]
            if not rows:
                return rows
            ids = [zeile["id"] for zeile in rows]
            cur.execute(
                "SELECT * FROM feedback_attachments WHERE feedback_id = ANY(%s) ORDER BY id",
                (ids,),
            )
            je_eintrag: dict[int, list[dict]] = {}
            for zeile in cur.fetchall():
                je_eintrag.setdefault(zeile["feedback_id"], []).append(dict(zeile))
            for eintrag in rows:
                eintrag["attachments"] = je_eintrag.get(eintrag["id"], [])
            return rows


def count_open_feedback() -> int:
    """Number of entries nobody has dealt with yet."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM feedback WHERE status = 'open'")
            return cur.fetchone()[0]


def set_feedback_status(feedback_id: int, status: str) -> bool:
    """Sets an entry to open, parked or done."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE feedback SET status = %s WHERE id = %s RETURNING id",
                (status, feedback_id),
            )
            getroffen = cur.fetchone() is not None
        conn.commit()
        return getroffen


def delete_feedback(feedback_id: int) -> bool:
    """Removes an entry, its attachment rows (cascade) and their stored files."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM feedback WHERE id = %s RETURNING id", (feedback_id,))
            getroffen = cur.fetchone() is not None
        conn.commit()
    if getroffen:
        storage.delete_feedback_attachments(feedback_id)
    return getroffen
