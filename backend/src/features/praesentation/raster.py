"""How many cards and bars a content field holds, from its size and text size alone."""

from __future__ import annotations

import math

EMU_PER_PT = 12700
MAX_KARTEN = 8
MAX_BALKEN = 8
# Card text follows the template's body size, but a poster-sized body would leave room for one card.
MAX_GRUND_PT = 18.0
STANDARD_PT = 16.0
# Card measures in multiples of the base size, taken from the example deck: a card as wide as
# three to a row on a wide slide, tall enough for icon, title and two lines of text.
KARTE_MIN_BREITE = 16.0
KARTE_MIN_HOEHE = 8.2
ABSTAND = 1.0
TITEL_ANTEIL = 1.05
TEXT_ANTEIL = 0.8
TEXTZEILEN = 3
# A bar row needs its label on up to two lines.
BALKEN_MIN_HOEHE = 2.2
_ZEICHEN_JE_WORT = 6.5


def grund_pt(size_pt: float) -> float:
    return min(MAX_GRUND_PT, size_pt or STANDARD_PT)


def _anzahl(laenge_pt: float, min_pt: float, abstand_pt: float) -> int:
    return max(1, int((laenge_pt + abstand_pt) // (min_pt + abstand_pt)))


def karten_raster(breite: int, hoehe: int, size_pt: float) -> tuple[int, int]:
    """Columns and rows of cards the field holds at their smallest readable size."""
    g = grund_pt(size_pt)
    return (_anzahl(breite / EMU_PER_PT, KARTE_MIN_BREITE * g, ABSTAND * g),
            _anzahl(hoehe / EMU_PER_PT, KARTE_MIN_HOEHE * g, ABSTAND * g))


def karten_platz(breite: int, hoehe: int, size_pt: float) -> dict:
    """The most cards the field takes, and the words a title and a text may have in the fullest grid."""
    spalten, reihen = karten_raster(breite, hoehe, size_pt)
    g = grund_pt(size_pt)
    karte_pt = (breite / EMU_PER_PT - ABSTAND * g * (spalten - 1)) / spalten
    innen = karte_pt - 2 * 1.2 * g
    titel = innen / (TITEL_ANTEIL * g * 0.5)
    text = innen / (TEXT_ANTEIL * g * 0.5) * TEXTZEILEN
    return {"max": min(MAX_KARTEN, spalten * reihen),
            "titel_woerter": max(2, int(titel / _ZEICHEN_JE_WORT)),
            "text_woerter": max(4, int(text / _ZEICHEN_JE_WORT))}


def verteilung(n: int, spalten_max: int) -> list[int]:
    """Cards per row: as few rows as the width allows, rows as even as possible, the fuller ones first."""
    if n <= 0:
        return []
    reihen = math.ceil(n / max(1, spalten_max))
    breit = math.ceil(n / reihen)
    aus, rest = [], n
    for r in range(reihen):
        k = min(breit, rest - (reihen - r - 1))
        k = max(1, min(k, math.ceil(rest / (reihen - r))))
        aus.append(k)
        rest -= k
    return aus


def balken_platz(hoehe: int, size_pt: float) -> int:
    g = grund_pt(size_pt)
    return min(MAX_BALKEN, _anzahl(hoehe / EMU_PER_PT, BALKEN_MIN_HOEHE * g, 0.0))
