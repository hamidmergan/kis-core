"""Der Tipp, der beim Lernen an der Aufgabe haengt.

Er kommt aus dem Aufruf, der die Aufgabe schreibt, und kostet damit nichts. Bis dahin
schickte der Tipp-Knopf eine Frage in den Chat: ein Modellaufruf pro Klick, Wartezeit,
und der Lernende stand danach im Chat statt in der Aufgabe.

Gespeichert wird er in ``extras``. Die JSONB-Spalte gibt es in beiden Tabellen und sie
laeuft schon von Vorrat zu Aufgabe zu Ansicht durch, also braucht der Tipp keine eigene
Spalte und keine Wanderung auf bestehenden Installationen.
"""


def attach_hint(item: dict, roh: dict) -> None:
    """Legt den Tipp aus der Modellantwort ``roh`` in ``item['extras']``.

    Wer keinen Tipp geliefert hat, bekommt auch keinen. Die Ansicht faellt dann auf den
    alten Chat-Weg zurueck, damit Aufgaben aus dem alten Vorrat bedienbar bleiben.
    """
    tipp = roh.get("tip")
    tipp = tipp.strip() if isinstance(tipp, str) else ""
    if not tipp:
        return
    extras = item.get("extras")
    if not isinstance(extras, dict):
        extras = {}
        item["extras"] = extras
    extras["tip"] = tipp
