import os
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def create_access_link(workspace_id: int, code: str, expires_at: datetime | None) -> dict:
    """Create an access link. Following it always joins as a learner: only the
    owner can hand out tutor rights, and only to a named person."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """INSERT INTO aia_access_links (workspace_id, code, expires_at)
                   VALUES (%s, %s, %s)
                   RETURNING id, workspace_id, code, expires_at, created_at""",
                (workspace_id, code, expires_at),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row)

def get_access_links_by_workspace(workspace_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, workspace_id, code, expires_at, created_at
                   FROM aia_access_links
                   WHERE workspace_id = %s
                   ORDER BY created_at ASC""",
                (workspace_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]

def delete_access_link(link_id: int, workspace_id: int) -> None:
    # Scope the delete to the owning workspace so a link_id from another
    # workspace cannot be deleted via a workspace the caller happens to own.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_access_links WHERE id = %s AND workspace_id = %s",
                (link_id, workspace_id),
            )
        conn.commit()

def get_workspace_by_access_link_code(code: str) -> tuple[dict, dict] | None:
    """Return (workspace, link) tuple if code is valid and not expired."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.*, al.id AS link_id, al.expires_at AS link_expires_at
                   FROM aia_access_links al
                   JOIN aia_workspaces m ON m.id = al.workspace_id
                   WHERE al.code = %s AND (al.expires_at IS NULL OR al.expires_at > NOW())""",
                (code,),
            )
            row = cur.fetchone()
    if not row:
        return None
    row = dict(row)
    link = {"id": row.pop("link_id"), "expires_at": row.pop("link_expires_at")}
    return row, link


# --- KI Tutor: Enrollments ---

