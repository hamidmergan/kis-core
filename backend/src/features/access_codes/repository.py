"""The access codes in the database."""
from datetime import datetime

import psycopg2.extras

from src.core.db.pool import get_connection


def create_code(
    *,
    code: str,
    label: str,
    role: str,
    custom_role_id: int | None,
    max_uses: int,
    valid_until: datetime,
    access_days: int,
    created_by: int,
) -> int:
    """Creates a code and returns its id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO access_codes
                       (code, label, role, custom_role_id, max_uses,
                        valid_until, access_days, created_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (code, label, role, custom_role_id, max_uses,
                 valid_until, access_days, created_by),
            )
            code_id = cur.fetchone()[0]
        conn.commit()
        return code_id


def list_codes() -> list[dict]:
    """All codes, newest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM access_codes ORDER BY created_at DESC")
            return [dict(zeile) for zeile in cur.fetchall()]


def get_code_by_code(code: str) -> dict | None:
    """Looks up a code by the string the user typed."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM access_codes WHERE code = %s", (code,))
            zeile = cur.fetchone()
            return dict(zeile) if zeile else None


def set_active(code_id: int, active: bool) -> bool:
    """Switches a code on or off, accounts stay untouched."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE access_codes SET active = %s WHERE id = %s RETURNING id",
                (active, code_id),
            )
            getroffen = cur.fetchone() is not None
        conn.commit()
        return getroffen


def delete_code(code_id: int) -> bool:
    """Removes the code, the foreign key empties access_code_id and keeps the accounts."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM access_codes WHERE id = %s RETURNING id", (code_id,))
            getroffen = cur.fetchone() is not None
        conn.commit()
        return getroffen


def claim_use(code_id: int) -> bool:
    """Takes one seat, only while the code is on, valid and not full."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE access_codes SET used_count = used_count + 1
                   WHERE id = %s AND active AND valid_until > NOW()
                     AND used_count < max_uses
                   RETURNING id""",
                (code_id,),
            )
            getroffen = cur.fetchone() is not None
        conn.commit()
        return getroffen


def release_use(code_id: int) -> None:
    """Gives the seat back when creating the account failed afterwards."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE access_codes SET used_count = used_count - 1 "
                "WHERE id = %s AND used_count > 0",
                (code_id,),
            )
        conn.commit()


def list_users_for_code(code_id: int) -> list[dict]:
    """Every account a code created, newest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, ldap_username, created_at, access_expires_at, active
                   FROM users WHERE access_code_id = %s ORDER BY created_at DESC""",
                (code_id,),
            )
            return [dict(zeile) for zeile in cur.fetchall()]


def set_user_access(user_id: int, *, expires_at: datetime | None, code_id: int | None) -> None:
    """Writes the deadline and the origin onto the account."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET access_expires_at = %s, access_code_id = %s WHERE id = %s",
                (expires_at, code_id, user_id),
            )
        conn.commit()


def list_workspaces_for_user(user_id: int) -> list[dict]:
    """Every module this account owns or joined, owned wins where both apply."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id AS workspace_id, title, created_at AS since
                   FROM aia_workspaces WHERE user_id = %s""",
                (user_id,),
            )
            eintraege = {zeile["workspace_id"]: {**dict(zeile), "relation": "owner"} for zeile in cur.fetchall()}
            cur.execute(
                """SELECT w.id AS workspace_id, w.title, e.created_at AS since
                   FROM aia_enrollments e JOIN aia_workspaces w ON w.id = e.workspace_id
                   WHERE e.user_id = %s""",
                (user_id,),
            )
            for zeile in cur.fetchall():
                eintraege.setdefault(zeile["workspace_id"], {**dict(zeile), "relation": "enrolled"})
    return sorted(eintraege.values(), key=lambda z: z["since"], reverse=True)


def list_messages_for_user(user_id: int, limit: int = 50) -> list[dict]:
    """This account's chat rounds across every module, newest first and capped so the query stays cheap."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.role, m.content, m.created_at, m.failed, m.aborted,
                          w.title AS workspace_title
                   FROM aia_messages m
                   JOIN aia_workspaces w ON w.id = m.workspace_id
                   WHERE m.user_id = %s
                   ORDER BY m.created_at DESC
                   LIMIT %s""",
                (user_id, limit),
            )
            return [dict(zeile) for zeile in cur.fetchall()]
