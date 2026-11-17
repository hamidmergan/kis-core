"""Database access for the key/value settings."""
import psycopg2.extras

from src.core.db.pool import get_connection


def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
            row = cur.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO settings (key, value)
                   VALUES (%s, %s)
                   ON CONFLICT (key) DO UPDATE
                   SET value = EXCLUDED.value,
                       updated_at = NOW()""",
                (key, value),
            )
        conn.commit()
