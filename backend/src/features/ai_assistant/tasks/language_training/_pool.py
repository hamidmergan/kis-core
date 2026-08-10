"""Aufgaben aus dem Vorrat holen und neu Erzeugtes einlagern.

Der Vorrat liegt an der Quelle und ist nach Werkzeug und Sprachniveau getrennt. Eine
Anfrage nimmt zuerst, was schon da ist und was diese Person noch nicht hatte; nur der
Fehlbetrag kostet einen Modellaufruf. Was dabei entsteht, wandert in den Vorrat und steht
ab dann allen im Kursraum offen.

Nicht jedes Werkzeug macht mit, siehe ``POOL_TOOLS``.
"""

from loguru import logger

from src import database as db
from src.features.ai_assistant.tasks.language_training._dedup import item_key

# Werkzeuge mit Vorrat. Die Grammatik-Uebung ist dabei, obwohl ihre Aufgaben zusaetzlich
# am gewaehlten Thema haengen: ihr Vorrat trennt deshalb auch danach. Das macht die
# einzelnen Vorraete kleiner, kostet aber nichts. Wiederholt sich eine Kombination nie,
# bleibt ihr Vorrat leer und die Anfrage ist genauso teuer wie vorher; wiederholt sie sich,
# was in einem Kurs mit einem festen Grammatikthema der Normalfall ist, ist sie umsonst.
POOL_TOOLS = frozenset({"flashcards", "karteikarten", "quiz", "grammatik"})

# Felder, die eine Vorratszeile mitbringt und eine Aufgabe im Satz braucht.
_CARRIED = (
    "front", "back", "back_en", "options", "correct_idx", "explanation",
    "source_label", "page_number", "start_time", "sources", "extras",
)


def uses_pool(tool: str, mode: str) -> bool:
    """Ob diese Anfrage ueber den Vorrat laeuft.

    Nur ``mode='source'``: der Glossar-Modus zieht aus einer fertigen Begriffsliste und
    hat das Problem, das der Vorrat loest, gar nicht.
    """
    return mode == "source" and tool in POOL_TOOLS


def pool_level(adaptive_suffix: str, user_id: int | None) -> str | None:
    """Das Niveau, unter dem diese Anfrage ein- und auslagert.

    Abgeleitet aus dem Zusatz statt aus dem Konto: der Zusatz ist genau dann leer, wenn
    eine der drei Schranken zu ist (Admin, Kursraum, Person) oder kein Niveau hinterlegt
    ist. Dann erzeugt das Werkzeug in seiner Grundformulierung, und die gehoert in den
    Vorrat ohne Niveau. So koennen Zusatz und Vorrat nicht auseinanderlaufen.
    """
    if not adaptive_suffix or not user_id:
        return None
    try:
        return db.get_user_language_level(user_id)["language_level"] or None
    except Exception:  # noqa: BLE001 - ohne Niveau ist der niveaulose Vorrat richtig
        return None


def _as_item(row: dict) -> dict:
    """Eine Vorratszeile in die Form bringen, die der Satz speichert."""
    item = {feld: row.get(feld) for feld in _CARRIED}
    item["pool_item_id"] = row["id"]
    return item


def take(uuids: list[str], tool: str, level, user_id: int, count: int,
         topic_id=None, kinds=None) -> list[dict]:
    """Bis zu ``count`` Aufgaben aus den Vorraeten der gewaehlten Quellen.

    Gleichmaessig auf die Quellen verteilt. Gibt eine Quelle weniger her, ruecken die
    anderen nach, statt dass die Anfrage unnoetig klein bleibt. Das ersetzt die alte
    Ausgleichsrechnung im Kontext, die dafuer die kleinste Quelle allen anderen als
    Groesse aufgezwungen hat.

    Ein Fehler beim Lesen liefert eine leere Liste. Der Vorrat ist eine Abkuerzung und
    keine Voraussetzung: faellt er aus, wird eben alles erzeugt, so wie vorher.

    ``kinds`` ist die Formatauswahl der Grammatik-Uebung und wird unveraendert an die
    Abfrage weitergereicht. Ohne sie holt der Vorrat wie bisher alles.
    """
    if not uuids or count <= 0 or not user_id:
        return []
    try:
        return _take(uuids, tool, level, user_id, count, topic_id, kinds)
    except Exception as e:  # noqa: BLE001
        logger.warning("KI Tutor: Vorrat nicht lesbar, es wird erzeugt: {}", e)
        return []


def _take(uuids: list[str], tool: str, level, user_id: int, count: int,
          topic_id=None, kinds=None) -> list[dict]:
    quellen = [db.get_aia_source(u) for u in uuids]
    source_ids = [q["id"] for q in quellen if q and q.get("id")]
    if not source_ids:
        return []
    offen = count
    genommen: list[dict] = []
    # Was diese Bestellung schon in der Hand hat. Die Abfrage weiss davon nichts, sie
    # laesst nur weg, was in einem gespeicherten Satz steckt, und der wird erst am Ende
    # geschrieben. Ohne diese beiden Merker holt die zweite Runde dasselbe noch einmal.
    geholt: list = []       # Vorrats-ids, gehen als Ausschluss in die naechste Abfrage
    texte: set[str] = set()  # deren Vergleichsformen, gegen Doppler ueber Quellen hinweg
    leer: set = set()        # Quellen, die weniger geliefert haben als bestellt
    # Zwei Runden: erst der gleiche Anteil fuer jede Quelle, dann der Rest an die, die
    # noch etwas haben.
    for runde in (1, 2):
        for i, source_id in enumerate(source_ids):
            if offen <= 0:
                break
            if source_id in leer:
                continue
            if runde == 1:
                uebrig = len(source_ids) - i
                will = min(offen, -(-offen // uebrig))  # aufgerundeter gleicher Anteil
            else:
                will = offen
            rows = db.take_from_pool(source_id, tool, level, user_id, will, topic_id,
                                     exclude_ids=geholt or None, kinds=kinds)
            if len(rows) < will:
                # Weniger als bestellt heisst: mehr hat dieser Vorrat nicht. Ein zweites
                # Mal zu fragen kostet nur eine Abfrage.
                leer.add(source_id)
            for row in rows:
                geholt.append(row["id"])
                # Zwei Quellen koennen dieselbe Aufgabe im Vorrat haben, der eindeutige
                # Index sitzt je Quelle.
                schluessel = item_key(row.get("front") or "")
                if schluessel:
                    if schluessel in texte:
                        continue
                    texte.add(schluessel)
                genommen.append(_as_item(row))
                offen -= 1
        if offen <= 0:
            break
    return genommen[:count]


def store(items: list[dict], ctx, tool: str, level, topic_id=None) -> None:
    """Frisch erzeugte Aufgaben einlagern und ihre Vorrats-id an ihnen vermerken.

    Zugeordnet wird ueber den Quellennamen, den die Attribution an die Aufgabe geschrieben
    hat. Eine Aufgabe ohne zuordenbare Quelle bleibt im Satz und traegt ihren Inhalt
    weiter selbst; sie geht nur nicht in den Vorrat, weil nicht feststeht, zu welcher
    Quelle sie gehoeren wuerde.

    Der Vorrat hat eine Obergrenze. Ist sie erreicht, wird nichts mehr eingelagert und die
    Aufgaben bleiben trotzdem im Satz.
    """
    if not items:
        return
    nach_quelle: dict[int, list[dict]] = {}
    for item in items:
        if item.get("pool_item_id"):
            continue  # kam schon aus dem Vorrat
        quelle = (ctx.source_by_name or {}).get(item.get("source_label") or "")
        if not quelle or not quelle.get("id"):
            continue
        nach_quelle.setdefault(quelle["id"], []).append(item)

    for source_id, gruppe in nach_quelle.items():
        try:
            platz = db.POOL_MAX_ITEMS - db.pool_size(source_id, tool, level, topic_id)
            if platz <= 0:
                continue
            gruppe = gruppe[:platz]
            ids = db.add_pool_items(
                source_id, tool, level, gruppe,
                [item_key(i.get("front", "")) for i in gruppe],
                topic_id,
            )
            for item, pool_id in zip(gruppe, ids):
                if pool_id:
                    item["pool_item_id"] = pool_id
        except Exception as e:  # noqa: BLE001
            # Einlagern ist eine Verbesserung fuer den naechsten Aufruf, keine
            # Voraussetzung fuer diesen. Der Satz ist fertig und wird gespeichert.
            logger.warning("KI Tutor: Vorrat der Quelle {} nicht gefuellt: {}", source_id, e)


__all__ = ["POOL_TOOLS", "pool_level", "store", "take", "uses_pool"]
