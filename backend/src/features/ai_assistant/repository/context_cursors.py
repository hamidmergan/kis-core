"""Where the last generation run stopped reading inside a source.

One row per workspace + source + tool, holding one cursor per coverage block. A
source that does not fit the context budget is read as a sweep rather than a
random draw, and these are the positions the sweep resumes from.

Kept out of ``exercises.py`` on purpose: the data table and the mindmap read
sources the same way and are not exercises.
"""

import json

from src.core.db.pool import get_connection


def get_context_cursors(workspace_id: int, source_id: int, tool: str) -> list[int]:
    """Cursors of the last run, or an empty list when this source is new to the tool.

    An empty list means "start at the beginning of every block", which is what a
    first run should do.
    """
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


__all__ = ["get_context_cursors", "set_context_cursors"]
