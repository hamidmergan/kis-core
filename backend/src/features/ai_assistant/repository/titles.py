"""Den Anzeigenamen eines erzeugten Ergebnisses aendern.

Drei Tabellen, eine Regel. Der Tabellenname kommt aus ``_TABLES`` und nie von
aussen, dieselbe Regel wie in ``source_rename.py``. Nur die Werte gehen als
Parameter in die Anweisung.

Anders als beim Umbenennen einer Quelle gibt es hier nichts nachzuziehen: der
Titel steht in genau einer Zeile und wird nirgends kopiert.
"""

from src.core.db.pool import get_connection

# Die Laenge, mit der die Titelspalten und die Oberflaeche rechnen.
MAX_TITLE_LEN = 120

_TABLES = {
    "exercise_set": "aia_exercise_sets",
    "mindmap": "aia_mindmaps",
    "data_table": "aia_data_tables",
}


def clean_title(title: str | None) -> str:
    """Getrimmt, innen auf einfache Leerzeichen gefaltet, auf die Obergrenze gekuerzt.

    Leer heisst hier leer: der Aufrufer lehnt das ab, statt einen Namen zu loeschen.
    """
    return " ".join((title or "").split())[:MAX_TITLE_LEN]


def update_artifact_title(kind: str, row_id: int, user_id: int, workspace_id: int,
                          title: str) -> bool:
    """True, wenn genau diese Zeile dieser Person in diesem Kursraum umbenannt wurde.

    Person und Kursraum stehen mit in der Bedingung und nicht in einer Pruefung
    davor. So gibt es kein Zeitfenster zwischen Pruefen und Schreiben, und der
    Aufrufer kann auf False einfach mit 404 antworten.
    """
    table = _TABLES[kind]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {table} SET title = %s "
                "WHERE id = %s AND user_id = %s AND workspace_id = %s",
                (title, row_id, user_id, workspace_id),
            )
            updated = cur.rowcount > 0
        conn.commit()
    return updated
