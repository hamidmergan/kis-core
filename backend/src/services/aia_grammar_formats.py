"""Die vier Darreichungsformen der Grammatik-Uebung und die Wahl darunter.

Steht hier und nicht im Trainer-Paket: die Route muss saeubern koennen, was der Browser
sendet, und alles unter ``tasks/language_training/`` zieht beim Import Celery mit. Ein
neutrales Modul spart der Web-Seite diesen Rattenschwanz.

Der Erzeuger holt seinen Katalog von hier. Zwei Kataloge waeren zwei Wahrheiten.
"""

# Die vier Darreichungsformen, in dieser Reihenfolge reihum verteilt. Das Format war
# frueher eine Wahl im Dialog, ist aber kein Thema, sondern eine Darreichungsform. Ein
# Lernender profitiert mehr davon, dieselbe Form auf vier Arten zu ueben als zehnmal
# auf eine, deshalb ist gemischt der Standard geblieben.
#
# Die Reihenfolge ist eine Entscheidung: geht die Anzahl nicht glatt auf, bekommen die
# vorderen Formate einen mehr. Vorne steht deshalb die Umformung, die das eigentliche
# Koennen prueft, hinten das Ankreuzen, das am meisten hilft.
KINDS = ("transform", "cloze", "statement", "choice")


def clean_kinds(roh) -> list[str] | None:
    """Die Auswahl in Katalogreihenfolge, oder ``None`` fuer gemischt.

    ``None`` heisst gemischt, und das ist der einzige Weg, gemischt auszudruecken.
    Deshalb wird auch "alle vier" zu ``None``: das IST gemischt, und ein zweiter
    Ausdruck fuer denselben Zustand waere ein Fall, den jede spaetere Abfrage
    mitdenken muesste.

    Unbekanntes wird weggeworfen statt abgewiesen. Ein Kuerzel, das dieses Backend
    nicht kennt, kommt von einem aelteren oder neueren Browser, und eine gemischte
    Uebung ist eine bessere Antwort als ein Fehler.
    """
    if not isinstance(roh, list):
        return None
    gewaehlt = {k for k in roh if isinstance(k, str) and k in KINDS}
    if not gewaehlt or len(gewaehlt) == len(KINDS):
        return None
    return [k for k in KINDS if k in gewaehlt]


__all__ = ["KINDS", "clean_kinds"]
