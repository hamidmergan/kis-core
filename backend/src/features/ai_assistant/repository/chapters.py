"""Chapters structure the source list, position is gapless and starts at 0."""

import psycopg2.extras

from src.core.db.pool import get_connection
from src.features.ai_assistant.repository.sources import SOURCE_LIST_ORDER


def get_aia_chapters_by_workspace(workspace_id: int) -> list[dict]:
    """Chapters of a course room in their order."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM aia_chapters
                   WHERE workspace_id = %s
                   ORDER BY position ASC, id ASC""",
                (workspace_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_aia_chapter(uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM aia_chapters WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    return dict(row) if row else None


def count_aia_chapters(workspace_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM aia_chapters WHERE workspace_id = %s",
                (workspace_id,),
            )
            return int(cur.fetchone()[0])


def create_aia_chapter(workspace_id: int, uuid: str, name: str) -> dict:
    """Neues Kapitel, haengt hinten an."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """INSERT INTO aia_chapters (workspace_id, uuid, name, position)
                   VALUES (
                       %s, %s, %s,
                       COALESCE(
                           (SELECT MAX(position) + 1 FROM aia_chapters WHERE workspace_id = %s),
                           0
                       )
                   )
                   RETURNING *""",
                (workspace_id, uuid, name, workspace_id),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row)


def rename_aia_chapter(uuid: str, name: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE aia_chapters SET name = %s WHERE uuid = %s", (name, uuid))
        conn.commit()


def delete_aia_chapter(uuid: str) -> None:
    """Delete a chapter, the sources in it stay and end up without a chapter."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_chapters WHERE uuid = %s RETURNING workspace_id",
                (uuid,),
            )
            row = cur.fetchone()
            if row:
                _renumber(cur, row[0])
        conn.commit()


def move_aia_chapter(uuid: str, direction: str) -> bool:
    """Move a chapter by one slot, returns False when it sits at the edge."""
    if direction not in ("up", "down"):
        return False
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, workspace_id, position FROM aia_chapters WHERE uuid = %s",
                (uuid,),
            )
            row = cur.fetchone()
            if not row:
                return False
            chapter_id, workspace_id, position = row
            # Renumber before the swap, older rows may have gaps.
            _renumber(cur, workspace_id)
            cur.execute("SELECT position FROM aia_chapters WHERE id = %s", (chapter_id,))
            position = cur.fetchone()[0]
            neighbour_position = position - 1 if direction == "up" else position + 1
            cur.execute(
                "SELECT id FROM aia_chapters WHERE workspace_id = %s AND position = %s",
                (workspace_id, neighbour_position),
            )
            neighbour = cur.fetchone()
            if not neighbour:
                return False
            cur.execute(
                "UPDATE aia_chapters SET position = %s WHERE id = %s",
                (position, neighbour[0]),
            )
            cur.execute(
                "UPDATE aia_chapters SET position = %s WHERE id = %s",
                (neighbour_position, chapter_id),
            )
        conn.commit()
    return True


def set_aia_source_chapter(source_uuid: str, chapter_id: int | None) -> None:
    """Assign a source to a chapter, ``None`` means no chapter, a new chapter puts it on top."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_sources
                   SET position = CASE WHEN chapter_id IS DISTINCT FROM %s THEN NULL ELSE position END,
                       chapter_id = %s
                   WHERE uuid = %s""",
                (chapter_id, chapter_id, source_uuid),
            )
        conn.commit()


def move_aia_source(uuid: str, direction: str) -> bool:
    """Move a source by one slot within its chapter, returns False at the edge."""
    if direction not in ("up", "down"):
        return False
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, workspace_id, chapter_id FROM aia_sources WHERE uuid = %s",
                (uuid,),
            )
            row = cur.fetchone()
            if not row:
                return False
            source_id, workspace_id, chapter_id = row
            cur.execute(
                f"""SELECT id FROM aia_sources
                    WHERE workspace_id = %s AND chapter_id IS NOT DISTINCT FROM %s
                    ORDER BY {SOURCE_LIST_ORDER}""",
                (workspace_id, chapter_id),
            )
            ids = [r[0] for r in cur.fetchall()]
            i = ids.index(source_id)
            j = i - 1 if direction == "up" else i + 1
            if j < 0 or j >= len(ids):
                return False
            ids[i], ids[j] = ids[j], ids[i]
            # The whole group gets numbers, unplaced rows would otherwise jump back on top.
            cur.execute(
                """UPDATE aia_sources SET position = array_position(%s::int[], id) - 1
                   WHERE id = ANY(%s::int[])""",
                (ids, ids),
            )
        conn.commit()
    return True


def _renumber(cur, workspace_id: int) -> None:
    """Renumber a course room's positions to 0..n-1."""
    cur.execute(
        """UPDATE aia_chapters c
           SET position = ranked.rn - 1
           FROM (
               SELECT id, ROW_NUMBER() OVER (ORDER BY position ASC, id ASC) AS rn
               FROM aia_chapters WHERE workspace_id = %s
           ) ranked
           WHERE c.id = ranked.id AND c.position <> ranked.rn - 1""",
        (workspace_id,),
    )
