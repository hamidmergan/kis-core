"""Pages of the campus index: crawled web pages, uploaded documents and places of the map."""
from datetime import datetime

import psycopg2.extras

from src.core.db.pool import get_connection

KIND_PAGE = "page"
KIND_DOCUMENT = "document"
KIND_PLACE = "place"

_COLS = "id, kind, url, title, filename, file_path, etag, last_modified, content_hash, status, error_message, chunk_count, fetched_at, created_at, updated_at"


def upsert_page(kind: str, url: str | None, title: str | None = None, filename: str | None = None, file_path: str | None = None) -> int:
    """Returns the id of the page with this url, creating it when new."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if url is not None:
                cur.execute("SELECT id FROM campus_pages WHERE url = %s", (url,))
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE campus_pages SET kind = %s, title = COALESCE(%s, title), updated_at = NOW() WHERE id = %s",
                        (kind, title, row[0]),
                    )
                    conn.commit()
                    return row[0]
            cur.execute(
                "INSERT INTO campus_pages (kind, url, title, filename, file_path) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (kind, url, title, filename, file_path),
            )
            page_id = cur.fetchone()[0]
        conn.commit()
    return page_id


def get_page(page_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT {_COLS} FROM campus_pages WHERE id = %s", (page_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_page_by_url(url: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT {_COLS} FROM campus_pages WHERE url = %s", (url,))
            row = cur.fetchone()
    return dict(row) if row else None


def set_page_fetch(page_id: int, etag: str | None, last_modified: str | None, fetched_at: datetime) -> None:
    """Remembers the validators of the last fetch, also when the page was unchanged."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE campus_pages SET etag = %s, last_modified = %s, fetched_at = %s, updated_at = NOW() WHERE id = %s",
                (etag, last_modified, fetched_at, page_id),
            )
        conn.commit()


def set_page_indexed(page_id: int, content_hash: str, title: str | None, chunk_count: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE campus_pages
                   SET content_hash = %s, title = COALESCE(%s, title), chunk_count = %s,
                       status = 'ready', error_message = NULL, updated_at = NOW()
                   WHERE id = %s""",
                (content_hash, title, chunk_count, page_id),
            )
        conn.commit()


def set_page_status(page_id: int, status: str, error_message: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE campus_pages SET status = %s, error_message = %s, updated_at = NOW() WHERE id = %s",
                (status, (error_message or "")[:500] or None, page_id),
            )
        conn.commit()


def list_page_urls(kind: str) -> dict[str, int]:
    """url -> id for every page of a kind, used to find pages that left the sitemap."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT url, id FROM campus_pages WHERE kind = %s AND url IS NOT NULL", (kind,))
            rows = cur.fetchall()
    return {url: page_id for url, page_id in rows}


def list_pages(kind: str) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT {_COLS} FROM campus_pages WHERE kind = %s ORDER BY created_at DESC, id DESC", (kind,))
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def delete_page(page_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM campus_pages WHERE id = %s", (page_id,))
        conn.commit()


def delete_pages_of_kind(kind: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM campus_pages WHERE kind = %s", (kind,))
            n = cur.rowcount
        conn.commit()
    return n


def page_stats() -> dict:
    """Counts per kind and status plus the chunk total, for the admin page."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT kind, status, COUNT(*) FROM campus_pages GROUP BY kind, status")
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM campus_chunks")
            chunks = cur.fetchone()[0]
            cur.execute("SELECT MAX(fetched_at) FROM campus_pages WHERE kind = %s", (KIND_PAGE,))
            last = cur.fetchone()[0]
    counts: dict[str, dict[str, int]] = {}
    for kind, status, n in rows:
        counts.setdefault(kind, {})[status] = n
    return {"pages": counts, "chunks": chunks, "last_fetched_at": last.isoformat() if last else None}
