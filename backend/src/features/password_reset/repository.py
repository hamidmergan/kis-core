"""The password reset links in the database."""
from datetime import datetime

import psycopg2.extras

from src.core.db.pool import get_connection


def create_token(*, token_hash: str, user_id: int, created_by: int | None, expires_at: datetime) -> None:
    """Stores a new link and closes every older open link of the same account."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE password_reset_tokens SET used_at = NOW() WHERE user_id = %s AND used_at IS NULL",
                (user_id,),
            )
            cur.execute(
                """INSERT INTO password_reset_tokens (token_hash, user_id, created_by, expires_at)
                   VALUES (%s, %s, %s, %s)""",
                (token_hash, user_id, created_by, expires_at),
            )
        conn.commit()


def get_by_hash(token_hash: str) -> dict | None:
    """Looks up a link by the hash of its key."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM password_reset_tokens WHERE token_hash = %s", (token_hash,))
            zeile = cur.fetchone()
            return dict(zeile) if zeile else None


def mark_used(token_id: int) -> bool:
    """Stamps the link as used, only while it is still open and not expired."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE password_reset_tokens SET used_at = NOW()
                   WHERE id = %s AND used_at IS NULL AND expires_at > NOW()
                   RETURNING id""",
                (token_id,),
            )
            getroffen = cur.fetchone() is not None
        conn.commit()
        return getroffen


def reopen(token_id: int) -> None:
    """Makes the link usable again after the password change failed."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE password_reset_tokens SET used_at = NULL WHERE id = %s", (token_id,))
        conn.commit()
