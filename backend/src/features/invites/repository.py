"""Die Einladungen in der Datenbank."""
from datetime import datetime

import psycopg2.extras

from src.core.db.pool import get_connection


def create_invite(
    *,
    token: str,
    email: str,
    uid: str,
    role: str,
    custom_role_id: int | None,
    created_by: int,
    expires_at: datetime,
) -> int:
    """Legt eine Einladung an und gibt ihre Kennung zurueck."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO invites
                       (token, email, uid, role, custom_role_id, created_by, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (token, email, uid, role, custom_role_id, created_by, expires_at),
            )
            invite_id = cur.fetchone()[0]
        conn.commit()
        return invite_id


def get_invite_by_token(token: str) -> dict | None:
    """Sucht eine Einladung ueber den Schluessel aus dem Link."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM invites WHERE token = %s", (token,))
            zeile = cur.fetchone()
            return dict(zeile) if zeile else None


def mark_invite_used(invite_id: int) -> bool:
    """Stempelt die Einladung als eingeloest, nur solange sie offen ist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE invites SET used_at = NOW()
                   WHERE id = %s AND used_at IS NULL
                   RETURNING id""",
                (invite_id,),
            )
            getroffen = cur.fetchone() is not None
        conn.commit()
        return getroffen


def list_invites() -> list[dict]:
    """Alle Einladungen, die neueste zuerst."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM invites ORDER BY created_at DESC")
            return [dict(zeile) for zeile in cur.fetchall()]


def delete_invite(invite_id: int) -> bool:
    """Zieht eine Einladung zurueck."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM invites WHERE id = %s RETURNING id", (invite_id,))
            getroffen = cur.fetchone() is not None
        conn.commit()
        return getroffen


def open_invite_for_email(email: str) -> dict | None:
    """Die noch offene Einladung an diese Adresse, falls es eine gibt."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM invites
                   WHERE LOWER(email) = LOWER(%s) AND used_at IS NULL AND expires_at > NOW()
                   ORDER BY created_at DESC LIMIT 1""",
                (email,),
            )
            zeile = cur.fetchone()
            return dict(zeile) if zeile else None


def reopen_invite(invite_id: int) -> None:
    """Nimmt den Stempel zurueck, wenn das Anlegen danach schiefgegangen ist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE invites SET used_at = NULL WHERE id = %s", (invite_id,))
        conn.commit()
