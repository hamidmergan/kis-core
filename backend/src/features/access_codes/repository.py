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


def set_user_access(user_id: int, *, expires_at: datetime | None, code_id: int | None) -> None:
    """Writes the deadline and the origin onto the account."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET access_expires_at = %s, access_code_id = %s WHERE id = %s",
                (expires_at, code_id, user_id),
            )
        conn.commit()
