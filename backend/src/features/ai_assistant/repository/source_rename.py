"""Eine Quelle umbenennen, samt aller Namenskopien im erzeugten Material.

Der Dateiname einer Quelle ist reiner Anzeigename. Die Datei selbst liegt unter
``file_path`` und heisst nach der UUID, Umbenennen fasst also keine gespeicherte
Datei an.

Was es anfassen muss, sind die Kopien. Aufgaben, Vorrat, Mindmaps und
Datentabellen schreiben den Namen zum Zeitpunkt ihrer Entstehung fest und finden
ihre Quelle spaeter ueber Namensgleichheit. Ohne Nachziehen verlieren die Chips
in altem Material ihr Ziel. Alles laeuft in einer Transaktion, damit nie ein halb
umbenannter Zustand stehen bleibt.

Eigenes Modul und nicht in ``sources.py``, weil hier vier fremde Tabellen
angefasst werden. Das ist eine eigene Aufgabe mit eigener Grenze.
"""

from psycopg2.extras import Json

from src.core.db.pool import get_connection

# Die beiden Schluessel, unter denen ein Quellenname wirklich steht.
# ``source_label`` in Aufgaben, Mindmap-Knoten und Tabellenzeilen,
# ``filename`` in der Quellenlegende einer Datentabelle.
_NAME_KEYS = ("source_label", "filename")


def _relabel(value, old: str, new: str):
    """Ersetzt in einer JSON-Struktur jeden Quellennamen ``old`` durch ``new``.

    Geht rekursiv durch Listen und Woerterbuecher, damit derselbe Durchlauf den
    Mindmap-Baum, die Zeilen einer Datentabelle und die Quellenliste einer
    Aufgabe trifft, ohne dass er ihre Form einzeln kennen muss. Ersetzt wird nur
    unter den Namensschluesseln. Ein Fliesstext, der zufaellig den alten Namen
    enthaelt, bleibt unangetastet.
    """
    if isinstance(value, list):
        return [_relabel(v, old, new) for v in value]
    if isinstance(value, dict):
        return {
            k: (new if k in _NAME_KEYS and v == old else _relabel(v, old, new))
            for k, v in value.items()
        }
    return value


def _relabel_column(cur, table: str, column: str, where: str, params: tuple, old: str, new: str) -> None:
    """Schreibt eine JSON-Spalte neu, in der Quellennamen als Kopie stehen.

    Der Umweg ueber Python statt ueber jsonb-Funktionen ist Absicht. Die
    Strukturen sind unterschiedlich tief verschachtelt, ein rekursiver Durchlauf
    trifft alle, ohne dass die Datenbank jede Form einzeln kennen muss.

    Tabellen- und Spaltennamen kommen ausschliesslich aus den festen Aufrufen
    unten, nie von aussen. Nur ``old``, ``new`` und ``params`` sind Werte und
    gehen als Parameter in die Anweisung.
    """
    cur.execute(f"SELECT id, {column} FROM {table} {where}", params)
    zeilen = cur.fetchall()
    for row_id, value in zeilen:
        if value is None:
            continue
        neu = _relabel(value, old, new)
        if neu != value:
            cur.execute(f"UPDATE {table} SET {column} = %s WHERE id = %s", (Json(neu), row_id))


def rename_aia_source(source_uuid: str, new_filename: str) -> None:
    """Benennt eine Quelle um und zieht jede Namenskopie mit.

    Still, wenn es die Quelle nicht gibt oder der Name schon stimmt. Der Aufrufer
    hat beides bereits geprueft, ein zweiter Fehler waere nur Laerm.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, workspace_id, filename FROM aia_sources WHERE uuid = %s",
                (source_uuid,),
            )
            row = cur.fetchone()
            if row is None:
                return
            source_id, workspace_id, old_filename = row[0], row[1], row[2]
            if old_filename == new_filename:
                return

            cur.execute(
                "UPDATE aia_sources SET filename = %s WHERE id = %s",
                (new_filename, source_id),
            )
            # Aufgaben haengen ueber ihren Satz am Kursraum, nicht an der Quelle.
            cur.execute(
                """UPDATE aia_exercise_items AS i SET source_label = %s
                     FROM aia_exercise_sets AS s
                    WHERE i.set_id = s.id
                      AND s.workspace_id = %s
                      AND i.source_label = %s""",
                (new_filename, workspace_id, old_filename),
            )
            # Der Vorrat haengt direkt an der Quelle. Hier braucht es keinen
            # Namensvergleich, jede Zeile dort gehoert ihr ohnehin.
            cur.execute(
                "UPDATE aia_exercise_pool SET source_label = %s WHERE source_id = %s",
                (new_filename, source_id),
            )

            _relabel_column(
                cur, "aia_exercise_items", "sources",
                "WHERE set_id IN (SELECT id FROM aia_exercise_sets WHERE workspace_id = %s)",
                (workspace_id,), old_filename, new_filename,
            )
            _relabel_column(
                cur, "aia_exercise_pool", "sources",
                "WHERE source_id = %s", (source_id,), old_filename, new_filename,
            )
            _relabel_column(
                cur, "aia_mindmaps", "mindmap",
                "WHERE workspace_id = %s", (workspace_id,), old_filename, new_filename,
            )
            _relabel_column(
                cur, "aia_data_tables", "table_data",
                "WHERE workspace_id = %s", (workspace_id,), old_filename, new_filename,
            )
            _relabel_column(
                cur, "aia_data_tables", "sources",
                "WHERE workspace_id = %s", (workspace_id,), old_filename, new_filename,
            )
        conn.commit()
