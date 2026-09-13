"""Remembers per source and tool where the last generation run stopped."""

import json

from src.core.db.pool import get_connection


def get_context_cursors(workspace_id: int, source_id: int, tool: str) -> list[int]:
    """The marks of the last run, empty means start from the beginning."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT cursors FROM aia_context_cursors
                   WHERE workspace_id = %s AND source_id = %s AND tool = %s""",
                (workspace_id, source_id, tool),
            )
            row = cur.fetchone()
    if not row or not row[0]:
        return []
    value = row[0]
    if isinstance(value, str):  # older psycopg2 setups hand JSONB back as text
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return [int(x) for x in value] if isinstance(value, list) else []


def set_context_cursors(
    workspace_id: int, source_id: int, tool: str, cursors: list[int],
) -> None:
    """Store the positions the next run continues from."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_context_cursors
                       (workspace_id, source_id, tool, cursors, updated_at)
                   VALUES (%s, %s, %s, %s, NOW())
                   ON CONFLICT (workspace_id, source_id, tool) DO UPDATE
                       SET cursors = EXCLUDED.cursors, updated_at = NOW()""",
                (workspace_id, source_id, tool, json.dumps(list(cursors))),
            )
        conn.commit()


def get_context_rotation(workspace_id: int, tool: str) -> int | None:
    """The source the next run starts at, ``None`` means the front of the list."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT next_source_id FROM aia_context_rotation
                   WHERE workspace_id = %s AND tool = %s""",
                (workspace_id, tool),
            )
            row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else None


def set_context_rotation(workspace_id: int, tool: str, source_id: int | None) -> None:
    """Store which source the next run starts at, ``None`` resets to the front."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_context_rotation
                       (workspace_id, tool, next_source_id, updated_at)
                   VALUES (%s, %s, %s, NOW())
                   ON CONFLICT (workspace_id, tool) DO UPDATE
                       SET next_source_id = EXCLUDED.next_source_id, updated_at = NOW()""",
                (workspace_id, tool, source_id),
            )
        conn.commit()


__all__ = [
    "get_context_cursors", "set_context_cursors",
    "get_context_rotation", "set_context_rotation",
]
