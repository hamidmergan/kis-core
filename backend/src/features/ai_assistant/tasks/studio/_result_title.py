"""Welche Zeilen ein Studio-Ergebnis dem Titel-Aufruf zeigt.

Der grosse Erzeugungs-Aufruf sieht das ganze Dokument und benennt deshalb das
Dokument. Der Titel-Aufruf bekommt hier nur das Ergebnis selbst, also das, was
zwei Mindmaps aus derselben Quelle tatsaechlich unterscheidet.

Die Titel-Logik dahinter liegt in ``tasks/_titles.py`` und ist fuer alle
Werkzeuge dieselbe.
"""

from src.core.db.pool import get_connection

# Nur die Tabellen, die einen Anzeigenamen tragen. Ein Tabellenname geht erst in die
# Abfrage, wenn er hier steht, dieselbe Regel wie in ``source_rename.py``.
_TITLE_TABLES = ("aia_mindmaps", "aia_data_tables")


def mindmap_entries(mindmap: dict) -> list[str]:
    """Die Knoten der ersten Ebene, ohne den Wurzelknoten.

    Der Wurzelknoten bleibt draussen: er ist genau der Dokumentname, von dem der
    Titel wegkommen soll.
    """
    kinder = (mindmap or {}).get("children") or []
    return [
        k["topic"].strip()
        for k in kinder
        if isinstance(k, dict) and str(k.get("topic") or "").strip()
    ]


def table_entries(table_data: dict) -> list[str]:
    """Spaltenkoepfe und die Werte der ersten Spalte.

    Die Koepfe sagen, worum es geht, die erste Spalte sagt, worueber konkret.
    """
    daten = table_data or {}
    eintraege = [str(c).strip() for c in (daten.get("columns") or []) if str(c or "").strip()]
    for zeile in daten.get("rows") or []:
        zellen = (zeile or {}).get("cells") or []
        if zellen and str(zellen[0] or "").strip():
            eintraege.append(str(zellen[0]).strip())
    return eintraege


def recent_titles(table: str, workspace_id: int | None, limit: int = 100) -> list[str]:
    """Die zuletzt vergebenen Titel dieses Werkzeugs im Kursraum, neueste zuerst.

    Leer bei fehlendem Kursraum oder Datenbankfehler: ein doppelter Name ist ein
    Schoenheitsfehler, nie ein Grund, ein fertiges Ergebnis fallen zu lassen.
    """
    if table not in _TITLE_TABLES or not workspace_id:
        return []
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT title FROM {table}
                        WHERE workspace_id = %s AND status = 'success'
                          AND title IS NOT NULL AND title <> ''
                        ORDER BY created_at DESC LIMIT %s""",
                    (workspace_id, limit),
                )
                return [r[0] for r in cur.fetchall() if r[0]]
    except Exception:  # noqa: BLE001
        return []
