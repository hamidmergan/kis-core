"""Der Aufgaben-Vorrat je Quelle, Werkzeug und Sprachniveau.

Aufgaben werden nicht mehr bei jedem Klick neu erzeugt. Was einmal entstanden ist, liegt
im Vorrat und steht allen im Kursraum offen. Eine Anfrage nimmt zuerst, was schon da ist
und was diese Person noch nicht hatte, und nur der Fehlbetrag kostet einen Modellaufruf.

Der Vorrat waechst als Nebenprodukt der Nutzung. Es gibt keinen Bau-Auftrag und keinen
Knopf, der ihn fuellt: was niemand anfordert, entsteht auch nicht.
"""

import json

import psycopg2.extras

from src.core.db.pool import get_connection

# Obergrenze je Vorrat, also je Quelle, Werkzeug und Niveau. Gibt die Quelle weniger her,
# bleibt der Vorrat kleiner; aufgefuellt wird nie mit Wiederholungen.
POOL_MAX_ITEMS = 1000

# Felder, die eine Aufgabe im Vorrat traegt. Ein Satz verweist nur noch hierher, deshalb
# muss der Vorrat alles halten, was die Anzeige braucht.
_ITEM_FIELDS = (
    "front", "back", "back_en", "options", "correct_idx", "explanation",
    "source_label", "page_number", "start_time", "sources", "extras",
)
_JSON_FIELDS = ("options", "sources", "extras")


def _as_row(item: dict, source_id: int, tool: str, level, topic_id, fingerprint: str) -> tuple:
    values = []
    for field in _ITEM_FIELDS:
        value = item.get(field)
        if field in _JSON_FIELDS:
            values.append(json.dumps(value) if value else None)
        else:
            values.append(value)
    return (source_id, tool, level, topic_id, fingerprint, *values)


def add_pool_items(
    source_id: int, tool: str, level, items: list[dict], fingerprints: list[str],
    topic_id=None,
) -> list[int]:
    """Aufgaben einlagern und die Vorrats-ids in derselben Reihenfolge zurueckgeben.

    Doppler werden vom eindeutigen Index abgefangen, nicht in Python: eine Aufgabe, die
    schon im Vorrat liegt, wird nicht ein zweites Mal geschrieben und liefert stattdessen
    die id der vorhandenen. Damit kann ein Satz auch auf eine Aufgabe zeigen, die jemand
    anderes erzeugt hat.
    """
    if not items:
        return []
    ids: list[int] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for item, fingerprint in zip(items, fingerprints):
                if not fingerprint:
                    ids.append(None)
                    continue
                cur.execute(
                    f"""INSERT INTO aia_exercise_pool
                        (source_id, tool, level, topic_id, fingerprint,
                         {", ".join(_ITEM_FIELDS)})
                        VALUES ({", ".join(["%s"] * (5 + len(_ITEM_FIELDS)))})
                        ON CONFLICT (source_id, tool, COALESCE(level, ''),
                                     COALESCE(topic_id, 0), fingerprint)
                        DO NOTHING
                        RETURNING id""",
                    _as_row(item, source_id, tool, level, topic_id, fingerprint),
                )
                row = cur.fetchone()
                if row is None:
                    # Lag schon drin, entweder aus einem frueheren Lauf oder von einer
                    # anderen Person. Wir nehmen die vorhandene Zeile.
                    cur.execute(
                        """SELECT id FROM aia_exercise_pool
                           WHERE source_id = %s AND tool = %s
                             AND COALESCE(level, '') = COALESCE(%s, '')
                             AND COALESCE(topic_id, 0) = COALESCE(%s, 0)
                             AND fingerprint = %s""",
                        (source_id, tool, level, topic_id, fingerprint),
                    )
                    row = cur.fetchone()
                ids.append(row[0] if row else None)
        conn.commit()
    return ids


def pool_size(source_id: int, tool: str, level, topic_id=None) -> int:
    """Wie viele Aufgaben in diesem Vorrat liegen."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM aia_exercise_pool
                   WHERE source_id = %s AND tool = %s
                     AND COALESCE(level, '') = COALESCE(%s, '')
                     AND COALESCE(topic_id, 0) = COALESCE(%s, 0)""",
                (source_id, tool, level, topic_id),
            )
            return cur.fetchone()[0]


def take_from_pool(
    source_id: int, tool: str, level, user_id: int, limit: int, topic_id=None,
    exclude_ids=None,
) -> list[dict]:
    """``limit`` Aufgaben aus dem Vorrat, die diese Person noch nicht hatte.

    Zufaellig gezogen und nicht der Reihe nach: sonst bekaeme jeder Neue immer denselben
    Anfang des Vorrats zu sehen, und der Rest bliebe liegen.

    "Noch nicht gehabt" heisst: die Aufgabe steckte in keinem Satz dieser Person. Der
    Vermerk haengt an der Aufgabe und nicht am Niveau, ein Aufstieg von A2 auf B1 bringt
    also nichts durcheinander.

    ``exclude_ids`` sind Zeilen, die derselbe Auftrag weiter oben schon geholt hat. Die
    Bedingung daneben sieht die nicht: sie prueft **gespeicherte** Saetze, und der Satz
    entsteht erst am Ende. Ohne diesen Ausschluss liefert ein zweiter Griff in denselben
    Vorrat noch einmal, was der erste schon hatte.
    """
    if limit <= 0:
        return []
    ausschluss = " AND p.id <> ALL(%s)" if exclude_ids else ""
    werte = [source_id, tool, level, topic_id, user_id]
    if exclude_ids:
        werte.append(list(exclude_ids))
    werte.append(limit)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""SELECT p.* FROM aia_exercise_pool p
                   WHERE p.source_id = %s AND p.tool = %s
                     AND COALESCE(p.level, '') = COALESCE(%s, '')
                     AND COALESCE(p.topic_id, 0) = COALESCE(%s, 0)
                     AND NOT EXISTS (
                       SELECT 1 FROM aia_exercise_items i
                       JOIN aia_exercise_sets s ON i.set_id = s.id
                       WHERE i.pool_item_id = p.id AND s.user_id = %s
                     ){ausschluss}
                   ORDER BY random()
                   LIMIT %s""",
                tuple(werte),
            )
            return [dict(row) for row in cur.fetchall()]


def seen_fingerprints(user_id: int, tool: str, limit: int = 2000) -> list[str]:
    """Vergleichsformen der Aufgaben, die diese Person in diesem Werkzeug schon hatte.

    Gebraucht fuer den Fehlbetrag: was frisch erzeugt wird, soll nicht das sein, was die
    Person letzte Woche schon bekommen hat. Der Vorrat filtert das ueber die Verweise,
    frisch Erzeugtes hat noch keine.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT i.front FROM aia_exercise_items i
                   JOIN aia_exercise_sets s ON i.set_id = s.id
                   WHERE s.user_id = %s AND s.tool = %s AND i.front <> ''
                   ORDER BY s.created_at DESC
                   LIMIT %s""",
                (user_id, tool, limit),
            )
            return [row[0] for row in cur.fetchall() if row[0]]


def _materialize(bedingung: str, wert) -> int:
    """Der gemeinsame Rueckschreib-Befehl. ``bedingung`` waehlt den Vorrat aus."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE aia_exercise_items i
                   SET back = p.back, back_en = p.back_en, options = p.options,
                       correct_idx = p.correct_idx, explanation = p.explanation,
                       source_label = p.source_label, page_number = p.page_number,
                       start_time = p.start_time, sources = p.sources, extras = p.extras
                   FROM aia_exercise_pool p
                   WHERE i.pool_item_id = p.id AND {bedingung}""",
                (wert,),
            )
            zurueck = cur.rowcount
        conn.commit()
    return zurueck


def materialize_pool_items(source_id: int) -> int:
    """Vorratsinhalt in die Saetze zurueckschreiben, die darauf zeigen.

    Muss laufen, BEVOR ein Vorrat verschwindet, also vor dem Loeschen der Quelle und vor
    dem Leeren beim Neu-Hochladen. Ein fertiger Aufgabensatz gehoert der Person, die ihn
    gemacht hat, und darf nicht leer werden, weil jemand die Quelle ausgetauscht hat.

    Gibt die Zahl der zurueckgeschriebenen Aufgaben zurueck.
    """
    return _materialize("p.source_id = %s", source_id)


def materialize_pool_items_for_topic(topic_id: int) -> int:
    """Dasselbe fuer den Vorrat eines Grammatikthemas.

    Gebraucht beim Entfernen des Themas: sein Vorrat haengt per Fremdschluessel daran
    und faellt mit. Die Saetze, die schon jemand gebaut hat, bleiben stehen und muessen
    ihren Inhalt vorher bekommen.
    """
    return _materialize("p.topic_id = %s", topic_id)


def clear_pool_for_source(source_id: int) -> int:
    """Vorrat einer Quelle wegwerfen. Gibt die Zahl der geloeschten Aufgaben zurueck.

    Beim Neu-Hochladen noetig: sonst bleiben Aufgaben zu einem Text stehen, den es so
    nicht mehr gibt. Der Inhalt wird vorher in die Saetze zurueckgeschrieben, die darauf
    zeigen, danach setzt der Fremdschluessel deren Verweis auf NULL.
    """
    materialize_pool_items(source_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_exercise_pool WHERE source_id = %s", (source_id,)
            )
            geloescht = cur.rowcount
        conn.commit()
    return geloescht


__all__ = [
    "POOL_MAX_ITEMS",
    "add_pool_items",
    "clear_pool_for_source",
    "materialize_pool_items",
    "pool_size",
    "seen_fingerprints",
    "take_from_pool",
]
