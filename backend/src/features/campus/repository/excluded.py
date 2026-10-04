"""Page addresses an admin took out of the index, the crawl skips them."""
from src.core.db.pool import get_connection


def list_urls() -> set[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT url FROM campus_excluded_urls")
            return {row[0] for row in cur.fetchall()}


def list_all() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT url, created_at FROM campus_excluded_urls ORDER BY created_at DESC, url")
            rows = cur.fetchall()
    return [{"url": url, "created_at": at.isoformat() if at else None} for url, at in rows]


def add(url: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO campus_excluded_urls (url) VALUES (%s) ON CONFLICT DO NOTHING", (url,))
        conn.commit()


def remove(url: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM campus_excluded_urls WHERE url = %s", (url,))
            n = cur.rowcount
        conn.commit()
    return n > 0
