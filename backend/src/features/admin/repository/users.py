import os
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def get_user_by_username(ldap_username: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE ldap_username = %s", (ldap_username,))
            return cur.fetchone()

def get_user_by_id(user_id: int):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()

def get_user_by_email(email: str):
    """Finds the account by its mail address, an empty address matches nobody."""
    wert = (email or "").strip()
    if not wert:
        return None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE LOWER(email) = LOWER(%s) ORDER BY id LIMIT 1",
                (wert,),
            )
            return cur.fetchone()


def create_user(
    ldap_username: str,
    display_name: str,
    email: str | None,
    active: int,
    role: str = "user",
    password_hash: str | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (ldap_username, display_name, email, active, role, password_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (ldap_username, display_name, email or None, active, role, password_hash),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
        return user_id

def update_user(user_id: int, display_name: str, email: str, active: int) -> None:
    """Changes the profile fields, the role goes through set_user_role."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET display_name = %s, email = %s, active = %s WHERE id = %s",
                (display_name, email, active, user_id),
            )
        conn.commit()


def update_user_locale(user_id: int, locale: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET locale = %s WHERE id = %s", (locale, user_id))
        conn.commit()


# --- Whitelist ---

def get_whitelist_emails() -> list[str]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT email FROM whitelist ORDER BY created_at")
            rows = cur.fetchall()
        return [row["email"] for row in rows]

def add_to_whitelist(email: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO whitelist (email) VALUES (%s) ON CONFLICT DO NOTHING",
                (email.strip().lower(),),
            )
        conn.commit()

def remove_from_whitelist(email: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM whitelist WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
        conn.commit()

def is_email_whitelisted(email: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM whitelist WHERE LOWER(email) = LOWER(%s)", (email.strip(),)
            )
            return cur.fetchone() is not None


# --- Settings (key/value store) ---

def get_all_users(
    limit: int = 50, offset: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
) -> tuple[list[dict], int]:
    """All users, newest first, as a pair of list and total count."""
    conditions = []
    params: list = []

    if q:
        like = f"%{q}%"
        conditions.append("(display_name ILIKE %s OR ldap_username ILIKE %s OR email ILIKE %s)")
        params += [like, like, like]
    if date_from:
        conditions.append("created_at >= %s::timestamp")
        params.append(_de_date_to_utc(date_from))
    if date_to:
        conditions.append("created_at <= %s::timestamp")
        params.append(_de_date_to_utc(date_to, end_of_day=True))

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()
            cur.execute(f"SELECT COUNT(*) AS total FROM users {where}", params)
            total = cur.fetchone()["total"]
    return [dict(row) for row in rows], total

def get_pending_users() -> list[dict]:
    """Users with active=0 (passed LDAP auth but not yet whitelisted)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE active = 0 ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [dict(row) for row in rows]

def activate_user(user_id: int) -> None:
    """Set active=1 for the given user."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET active = 1 WHERE id = %s", (user_id,))
        conn.commit()


def set_user_password(user_id: int, password_hash: str | None) -> None:
    """Sets the hash, None takes the form login away from the account."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id)
            )
        conn.commit()

def set_user_demo(user_id: int, is_demo: bool) -> list[int]:
    """Sets exactly one demo account and reports who lost the flag doing so."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if is_demo:
                cur.execute(
                    "UPDATE users SET is_demo = (id = %s) WHERE is_demo OR id = %s "
                    "RETURNING id, is_demo",
                    (user_id, user_id),
                )
                verloren = [zeile[0] for zeile in cur.fetchall() if not zeile[1]]
            else:
                cur.execute(
                    "UPDATE users SET is_demo = FALSE WHERE id = %s AND is_demo RETURNING id",
                    (user_id,),
                )
                verloren = [zeile[0] for zeile in cur.fetchall()]
        conn.commit()
    return verloren

def deactivate_user_by_email(email: str) -> None:
    """Set active=0 for any user with the given email."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET active = 0 WHERE LOWER(email) = LOWER(%s)", (email.strip(),)
            )
        conn.commit()


def ensure_local_admin() -> int:
    """Create the local admin user if it doesn't exist yet. Returns user_id."""
    existing = get_user_by_username("local")
    if existing:
        return existing["id"]
    return create_user(
        ldap_username="local",
        display_name="Admin",
        email="",
        active=1,
        role="admin",
    )



def set_user_tour_seen(user_id: int, seen: bool) -> None:
    """Marks the tour as done, or releases it again so the invitation returns."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET tour_seen_at = %s WHERE id = %s",
                (datetime.now() if seen else None, user_id),
            )
        conn.commit()


def set_user_tools_tour_seen(user_id: int, seen: bool) -> None:
    """Same for the tour through the tools, kept apart so one does not silence the other."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET tools_tour_seen_at = %s WHERE id = %s",
                (datetime.now() if seen else None, user_id),
            )
        conn.commit()


def demo_seeding_done(user_id: int) -> bool:
    """Whether this account already had its one demo assignment."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT demo_seeded_at IS NOT NULL FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return bool(row and row[0])


def claim_demo_seeding(user_id: int) -> bool:
    """Sets the mark and reports whether this call was the one that got it."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET demo_seeded_at = %s "
                "WHERE id = %s AND demo_seeded_at IS NULL RETURNING id",
                (datetime.now(), user_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row is not None
