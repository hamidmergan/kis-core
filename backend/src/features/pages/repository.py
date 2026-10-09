"""The share switch of each page and the one collection link of each person."""

from __future__ import annotations

import secrets

import psycopg2.extras

from src.core.db.pool import get_connection

# No letters a reader mixes up when typing a link off a slide.
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 16


def new_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))


def list_pages(user_id: int) -> list[dict]:
    """Every page of a person with its share state, newest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT j.job_uuid, j.status, j.progress, j.original_filename, j.result_filename,
                          j.error_message, j.created_at, j.completed_at,
                          s.code, COALESCE(s.enabled, FALSE) AS shared, COALESCE(s.public, FALSE) AS public
                   FROM jobs j LEFT JOIN page_shares s ON s.job_uuid = j.job_uuid
                   WHERE j.user_id = %s AND j.tool = 'pages'
                   ORDER BY j.created_at DESC""",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def count_pages(user_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs WHERE user_id = %s AND tool = 'pages'", (user_id,))
            return cur.fetchone()[0]


def get_share(job_uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT code, enabled, public, updated_at FROM page_shares WHERE job_uuid = %s",
                        (job_uuid,))
            row = cur.fetchone()
            return dict(row) if row else None


def set_share(job_uuid: str, user_id: int, on: bool, public: bool | None = None) -> dict:
    """Switches sharing, the code is made once and kept for every later switch.

    ``public`` None keeps who the link opens for, so the switch on a card leaves it as it was.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO page_shares (job_uuid, user_id, code, enabled, public)
                   VALUES (%s, %s, %s, %s, COALESCE(%s, FALSE))
                   ON CONFLICT (job_uuid) DO UPDATE SET enabled = EXCLUDED.enabled,
                       public = COALESCE(%s, page_shares.public), updated_at = NOW()
                   RETURNING code, enabled, public""",
                (job_uuid, user_id, new_code(), on, public, public),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row)


def shared_page(code: str) -> dict | None:
    """The page behind a share code, with its owner, None when it is off or gone."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT j.job_uuid, j.user_id, j.status, s.public, u.display_name AS owner_name,
                          CASE WHEN c.enabled THEN c.code END AS collection_code
                   FROM page_shares s
                   JOIN jobs j ON j.job_uuid = s.job_uuid
                   JOIN users u ON u.id = j.user_id
                   LEFT JOIN page_collections c ON c.user_id = j.user_id
                   WHERE s.code = %s AND s.enabled AND j.tool = 'pages'""",
                (code,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def page_by_code(code: str) -> dict | None:
    """The page behind a share code whether shared or not, so its owner can still use an old link."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT j.job_uuid, j.user_id FROM page_shares s
                   JOIN jobs j ON j.job_uuid = s.job_uuid
                   WHERE s.code = %s AND j.tool = 'pages'""",
                (code,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def collection_code(user_id: int) -> str:
    """The person's collection link, made on first use."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM page_collections WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                return row[0]
            for _ in range(5):
                cur.execute(
                    """INSERT INTO page_collections (user_id, code) VALUES (%s, %s)
                       ON CONFLICT DO NOTHING RETURNING code""",
                    (user_id, new_code()),
                )
                row = cur.fetchone()
                if row:
                    conn.commit()
                    return row[0]
                cur.execute("SELECT code FROM page_collections WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                if row:
                    return row[0]
    raise RuntimeError("collection code not stored")


def collection_shared(user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT enabled FROM page_collections WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return bool(row and row[0])


def set_collection_share(user_id: int, on: bool) -> bool:
    """Switches the collection link, its code stays the same."""
    collection_code(user_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE page_collections SET enabled = %s WHERE user_id = %s RETURNING enabled",
                        (on, user_id))
            row = cur.fetchone()
        conn.commit()
        return bool(row and row[0])


def collection(code: str, only_public: bool = False) -> dict | None:
    """The owner behind a collection link and every page they share, None for an unknown link.

    ``only_public`` leaves out what only a KIS account may read.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT c.user_id, c.enabled, u.display_name AS owner_name FROM page_collections c
                   JOIN users u ON u.id = c.user_id WHERE c.code = %s""",
                (code,),
            )
            owner = cur.fetchone()
            if not owner:
                return None
            cur.execute(
                """SELECT j.job_uuid, j.result_filename, s.code, s.updated_at, j.completed_at
                   FROM page_shares s JOIN jobs j ON j.job_uuid = s.job_uuid
                   WHERE j.user_id = %s AND s.enabled AND j.tool = 'pages' AND j.status = 'success'
                     AND (s.public OR NOT %s)
                   ORDER BY j.created_at DESC""",
                (owner["user_id"], only_public),
            )
            return {**dict(owner), "pages": [dict(r) for r in cur.fetchall()]}


def count_shared(user_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM page_shares s JOIN jobs j ON j.job_uuid = s.job_uuid
                   WHERE s.user_id = %s AND s.enabled AND j.status = 'success'""",
                (user_id,),
            )
            return cur.fetchone()[0]


def linked_sources(job_uuid: str) -> list[dict]:
    """Every workspace source that stands for this page, to read it again after a save."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT uuid, file_path, status FROM aia_sources WHERE source_url = %s",
                        (f"pages:{job_uuid}",))
            return [dict(r) for r in cur.fetchall()]
