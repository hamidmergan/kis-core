import os
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def create_aia_mindmap(workspace_id: int, user_id: int, source_ids: list[int],
                       user_instruction: str | None = None) -> int:
    """Create a pending mindmap record, return its id."""
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_mindmaps (workspace_id, user_id, source_ids, status,
                                             user_instruction)
                   VALUES (%s, %s, %s, 'pending', %s) RETURNING id""",
                (workspace_id, user_id, _json.dumps(source_ids), user_instruction or None),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]

def update_aia_mindmap(mindmap_id: int, status: str, mindmap: dict | None = None,
                       error: str | None = None, title: str | None = None) -> None:
    """Writes status and result, the title only when one is passed."""
    import json as _json
    zusatz = ", title = %s" if title is not None else ""
    werte: list = [status, _json.dumps(mindmap) if mindmap else None, error]
    if title is not None:
        werte.append(title)
    werte.append(mindmap_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE aia_mindmaps
                   SET status = %s, mindmap = %s, error = %s{zusatz}, updated_at = NOW()
                   WHERE id = %s""",
                tuple(werte),
            )
        conn.commit()

def get_aia_mindmap(mindmap_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_mindmaps WHERE id = %s", (mindmap_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_latest_aia_mindmap(workspace_id: int, user_id: int) -> dict | None:
    """Get the most recent mindmap for a workspace/user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM aia_mindmaps
                   WHERE workspace_id = %s AND user_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (workspace_id, user_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None

def get_all_aia_mindmaps(workspace_id: int, user_id: int) -> list[dict]:
    """All finished mind maps of a course room, newest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, status, created_at, user_instruction,
                          COALESCE(title, mindmap->>'topic') AS topic
                   FROM aia_mindmaps
                   WHERE workspace_id = %s AND user_id = %s AND status = 'success'
                   ORDER BY created_at DESC""",
                (workspace_id, user_id),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]

def delete_aia_mindmap(mindmap_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_mindmaps WHERE id = %s", (mindmap_id,))
        conn.commit()


# --- KI Tutor: DataTables ---

