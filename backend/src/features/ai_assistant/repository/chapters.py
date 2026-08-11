"""Kapitel im Quellenbereich eines Kursraums.

Ein Kapitel ist reine Gliederung: es gruppiert Quellen in der Liste und traegt
sonst nichts. Es entscheidet nicht, was der Chat oder ein Werkzeug zu sehen
bekommt, das haengt weiterhin allein am Haken der einzelnen Datei.

``position`` ist luecklos und beginnt bei 0. Jede Aenderung an der Reihenfolge
schreibt die Nummern des Kursraums neu, damit "nach oben" und "nach unten" nie
auf zwei gleiche Nummern trifft.
"""

import psycopg2.extras

from src.core.db.pool import get_connection


def get_aia_chapters_by_workspace(workspace_id: int) -> list[dict]:
    """Kapitel eines Kursraums in ihrer Reihenfolge."""
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
    """Kapitel loeschen. Die Quellen darin bleiben und stehen danach ohne Kapitel."""
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
    """Kapitel um einen Platz verschieben. Gibt False zurueck, wenn es am Rand steht."""
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
            # Vor dem Tausch aufraeumen: aeltere Zeilen koennen aus einer Zeit
            # stammen, in der noch nicht neu nummeriert wurde.
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
    """Quelle einem Kapitel zuordnen. ``None`` heisst "Ohne Kapitel"."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_sources SET chapter_id = %s WHERE uuid = %s",
                (chapter_id, source_uuid),
            )
        conn.commit()


def _renumber(cur, workspace_id: int) -> None:
    """Positionen eines Kursraums auf 0..n-1 zurechtruecken."""
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
