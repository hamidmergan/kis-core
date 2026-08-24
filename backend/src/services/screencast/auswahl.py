"""Welche Folien in den Screencast kommen und welche ihren alten Ton behalten."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Auswahl:
    """Die drei Sichten auf dieselbe Entscheidung, damit niemand sie neu rechnet."""

    clip_folien: list[int]
    ausgeschlossen: set[int]
    alter_ton_erlaubt: set[int]


def folien_auswahl(
    anzahl: int,
    video_folien: list[int] | None,
    neu_vertonen: list[int] | None,
) -> Auswahl:
    """``video_folien`` gleich None heisst alle Folien.

    Nummern ausserhalb des Bereichs fallen weg. Die Route lehnt sie schon ab,
    hier steht es nochmal, damit ein alter Auftrag aus der Warteschlange die
    Pipeline nicht zerlegt.
    """
    alle = set(range(anzahl))
    dabei = alle if video_folien is None else {i for i in video_folien if i in alle}
    neu = {i for i in (neu_vertonen or []) if i in alle}
    return Auswahl(
        clip_folien=sorted(dabei),
        ausgeschlossen=alle - dabei,
        alter_ton_erlaubt=dabei - neu,
    )
