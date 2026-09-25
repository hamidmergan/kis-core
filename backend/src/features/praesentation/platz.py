"""Room below a slide's heading: measured on the heading's real text, so a long one pushes the content down."""

from __future__ import annotations

from dataclasses import replace

from src.features.praesentation.teilung import zeilen
from src.features.praesentation.vorlage import EMU_PER_PT, Feld
from src.services.screencast.pptx import _load_font

# Air between the heading's last line and the content, in lines of the content's own text.
LUFT_ZEILEN = 1.0
_ZEILE = 1.2
# A content area keeps at least this share of its height however far a long heading pushes it.
_MIN_RESTANTEIL = 0.5
_UNTER_KOPF = ("fliesstext", "zwischentitel", "bild")


def zeilenhoehe(feld: Feld, groesse: float) -> float:
    """Line pitch in points: the template's fixed pitch scaled with the font, else the usual 1.2."""
    if feld.zeile_pt and feld.size_pt:
        return feld.zeile_pt * groesse / feld.size_pt
    return groesse * _ZEILE


def kopf_zeilen(text: str, feld: Feld, typeface: str, groesse: float) -> int:
    gemessen = text.upper() if feld.caps else text
    font = _load_font(f"{typeface}:bold" if feld.bold else typeface, round(groesse))
    return zeilen([gemessen], font, (feld.width - feld.inset_h) / EMU_PER_PT)


def kopf_unten(feld: Feld, text: str, typeface: str, groesse: float) -> int:
    """Where the heading's text ends on the slide, below its box when it runs over."""
    hoehe = int(kopf_zeilen(text, feld, typeface, groesse) * zeilenhoehe(feld, groesse) * EMU_PER_PT)
    if feld.anker == "b":
        return feld.top + feld.height - feld.inset_unten
    if feld.anker == "ctr":
        return feld.top + (feld.height + hoehe) // 2
    return feld.top + feld.inset_oben + hoehe


def darunter(felder: list[Feld], kopf: Feld) -> list[Feld]:
    return [f for f in felder if f.art in _UNTER_KOPF and f.top >= kopf.top + kopf.height // 2]


def verschoben(felder: list[Feld], kopf: Feld, unten: int, luft: int, folie_hoehe: int) -> dict[int, Feld]:
    """The fields below the heading moved so they start ``luft`` below its text, by placeholder index.

    The area keeps its bottom and gets shorter, down to half its height, beyond that it moves as a
    whole. A row of subheadings alone only ever moves, it has no height to give.
    """
    unter = darunter(felder, kopf)
    if not unter:
        return {}
    oben_alt = min(f.top for f in unter)
    unten_alt = max(f.top + f.height for f in unter)
    ziel = unten + luft
    if ziel <= oben_alt:
        return {}
    spanne = unten_alt - oben_alt
    anteil = 1.0 if all(f.art == "zwischentitel" for f in unter) else _MIN_RESTANTEIL
    neu = max(unten_alt - ziel, int(spanne * anteil))
    neu = max(0, min(neu, folie_hoehe - ziel))
    faktor = neu / spanne if spanne else 1.0
    return {f.idx: replace(f, top=ziel + int((f.top - oben_alt) * faktor), height=int(f.height * faktor))
            for f in unter}


def luft(felder: list[Feld]) -> int:
    """One line of the content's own text, taken from the first text field below the heading."""
    groesse = next((f.size_pt for f in felder if f.art == "fliesstext" and f.size_pt), 0.0) or next(
        (f.size_pt for f in felder if f.art == "zwischentitel" and f.size_pt), 16.0)
    return int(LUFT_ZEILEN * groesse * _ZEILE * EMU_PER_PT)
