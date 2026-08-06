"""Der Aufgabenplan eines Sets: welche Art wie oft, und was davon noch fehlt.

Zwei Werkzeuge bestellen ihre Aufgaben nach Arten gemischt, die Grammatik-Übung nach
Darreichungsform und das Hör- und Leseverstehen nach Frageart. Beide brauchen dieselben
drei Handgriffe, deshalb stehen sie hier und nicht zweimal:

* :func:`plan_sentence` schreibt den Plan als ZAHLENSATZ in den Prompt. Gemessen an
  beiden Werkzeugen: "stelle abwechslungsreiche Aufgaben" wirkt nicht, "genau 4 Aufgaben
  der Art X" wirkt.
* :func:`room_left` deckelt einen Wurf je Art, damit die Mischung nicht schon im ersten
  Wurf kippt.
* :func:`still_missing` sagt dem Nachschlag, wonach er gezielt fragen soll.

Eine Aufgabe trägt ihre Art im Hilfsfeld ``_kind``, das vor dem Speichern wieder
entfernt wird.
"""


def plan_sentence(plan: list[str]) -> str:
    """Der Plan als Zahlensatz für den Prompt. Gezählt statt beschrieben."""
    return ", ".join(f'{n} of kind "{kind}"' for kind, n in _counted(plan).items())


def room_left(plan: list[str], have: list[dict]) -> dict:
    """Wie viele Aufgaben je Art noch in den Plan passen."""
    want = _counted(plan)
    for item in have:
        kind = item.get("_kind")
        if kind in want:
            want[kind] -= 1
    return {kind: max(0, n) for kind, n in want.items()}


def still_missing(plan: list[str], have: list[dict]) -> list[str]:
    """Welche Arten noch fehlen, als Plan für den nächsten Wurf.

    Herauskommt wieder eine Liste in der Reihenfolge des Plans, die
    :func:`plan_sentence` als Zahlensatz in den Prompt schreibt.
    """
    room = room_left(plan, have)
    out: list[str] = []
    for kind in _counted(plan):
        out.extend([kind] * room.get(kind, 0))
    return out


def _counted(plan: list[str]) -> dict:
    """Der Plan als Zählung, in der Reihenfolge seines ersten Auftretens."""
    counts: dict[str, int] = {}
    for kind in plan:
        counts[kind] = counts.get(kind, 0) + 1
    return counts
