"""Splits an overfull slide in two when both halves keep enough points, else the text shrinks."""

from __future__ import annotations

import re

from src.features.praesentation.schemas import Body, Column, Slide
from src.features.praesentation.store import neue_id
from src.features.praesentation.vorlage import EMU_PER_PT, Analyse, Feld
from src.services.screencast.pptx import _load_font

_INSET_PT = 36.0
_BULLET_PT = 22.0
_ZEILE = 1.2
# A slide with fewer points is not worth showing, a field beside another needs fewer.
MIN_PUNKTE = 5
MIN_PUNKTE_JE_SPALTE = 3
# Shrinking stops here, below this a room at the back can no longer read the text.
MIN_SCHRIFT_PT = 12


def zeilen(items: list[str], font, breite_pt: float) -> int:
    """Greedy word wrap over every point, the same way PowerPoint breaks lines."""
    n = 0
    for item in items:
        n += 1
        aktuell = 0.0
        for wort in item.split():
            w = font.getlength(wort)
            leer = font.getlength(" ") if aktuell else 0.0
            if aktuell and aktuell + leer + w > breite_pt:
                n += 1
                aktuell = w
            else:
                aktuell += leer + w
    return n


def passt(items: list[str], feld: Feld, typeface: str, groesse: float | None = None) -> bool:
    if not items:
        return True
    groesse = groesse or feld.size_pt
    font = _load_font(typeface, round(groesse))
    breite = feld.width / EMU_PER_PT - _INSET_PT - _BULLET_PT
    hoehe = feld.height / EMU_PER_PT - 7.0
    return zeilen(items, font, breite) * groesse * _ZEILE <= hoehe


def schriftgrad(items: list[str], feld: Feld, typeface: str) -> float | None:
    """The largest size at which the points fit, None when the field's own size already does."""
    if passt(items, feld, typeface):
        return None
    groesse = float(round(feld.size_pt)) - 1
    while groesse > MIN_SCHRIFT_PT and not passt(items, feld, typeface, groesse):
        groesse -= 1
    return max(groesse, MIN_SCHRIFT_PT)


def _engste(a: Analyse, rolle: str, n: int) -> list[Feld] | None:
    """Per position the smallest text field across the layouts of the role, the safe measure."""
    kandidaten = [a.layout(i).der_art("fliesstext") for i in a.rollen.get(rolle, [])]
    kandidaten = [k for k in kandidaten if len(k) >= n]
    if not kandidaten:
        return None
    return [min((k[i] for k in kandidaten), key=lambda f: f.width * f.height) for i in range(n)]


def _felder(s: Slide, a: Analyse, n: int) -> list[Feld] | None:
    """The slide's own text fields once its layout is fixed, else the narrowest of its role."""
    if s.layout is not None:
        layout = next((l for l in a.layouts if l.index == s.layout), None)
        eigene = layout.der_art("fliesstext") if layout else []
        if len(eigene) >= n:
            return eigene[:n]
    return _engste(a, s.role, n)


_BILD_ROLLEN = ("text_mit_bild", "bild_gross")
# A sentence ends behind a word of three or more characters, so abbreviations like "z. B." stay whole.
_SATZENDE = re.compile(r"(?<=\w{3}[.!?])\s+")


def notizen_teilen(notes: str, anteil: float) -> tuple[str, str]:
    """The notes cut at the sentence end nearest the share of points the first half keeps, each half keeps at least one sentence."""
    saetze = _SATZENDE.split(notes.strip())
    if len(saetze) < 2:
        return notes, notes
    ziel = anteil * len(notes)
    stand, schnitt, abstand = 0, 1, float("inf")
    for i, satz in enumerate(saetze[:-1], 1):
        stand += len(satz) + 1
        if abs(stand - ziel) < abstand:
            schnitt, abstand = i, abs(stand - ziel)
    return " ".join(saetze[:schnitt]), " ".join(saetze[schnitt:])


def _rest_form(s: Slide, a: Analyse) -> tuple[str, int | None]:
    """Role and layout of a split-off part, a picture slide's rest carries text only."""
    if s.role not in _BILD_ROLLEN:
        return s.role, s.layout
    rolle = "zwei_spalten" if s.columns else "text"
    kandidaten = a.rollen.get(rolle) or []
    return rolle, (kandidaten[0] if kandidaten else None)


def _abgeschnitten(s: Slide, a: Analyse) -> Slide | None:
    """Moves the second half of the points to a new slide, None when everything fits."""
    if s.body and s.body.kind == "bullets" and len(s.body.items) >= 2 * MIN_PUNKTE:
        felder = _felder(s, a, 1)
        if felder and not passt(s.body.items, felder[0], a.typeface):
            mitte = (len(s.body.items) + 1) // 2
            # Each half speaks about its own points, no slide may end up without speaker text.
            s.notes, rest_notes = notizen_teilen(s.notes, mitte / len(s.body.items))
            rolle, layout = _rest_form(s, a)
            rest = Slide(role=rolle, layout=layout, title=s.title, notes=rest_notes,
                         body=Body(kind="bullets", items=s.body.items[mitte:]))
            s.body.items = s.body.items[:mitte]
            return rest
    if s.columns and all(len(c.items) >= 2 * MIN_PUNKTE_JE_SPALTE for c in s.columns):
        felder = _felder(s, a, len(s.columns))
        if felder and any(not passt(c.items, f, a.typeface) for c, f in zip(s.columns, felder)):
            gesamt = sum(len(c.items) for c in s.columns)
            s.notes, rest_notes = notizen_teilen(
                s.notes, sum((len(c.items) + 1) // 2 for c in s.columns) / gesamt)
            rolle, layout = _rest_form(s, a)
            rest = Slide(role=rolle, layout=layout, title=s.title, notes=rest_notes, columns=[
                Column(heading=c.heading, items=c.items[(len(c.items) + 1) // 2:]) for c in s.columns])
            for c in s.columns:
                c.items = c.items[:(len(c.items) + 1) // 2]
            return rest
    return None


def teile_ueberlauf(slides: list[Slide], a: Analyse) -> list[Slide]:
    """Every slide is split until each part fits, the parts keep their order."""
    out: list[Slide] = []
    ids = {s.id for s in slides}
    for s in slides:
        stapel = [s]
        while stapel:
            aktuell = stapel.pop()
            rest = _abgeschnitten(aktuell, a)
            if rest is None:
                out.append(aktuell)
                continue
            rest.id = neue_id(ids)
            ids.add(rest.id)
            # The rest waits below the first half, so the first half is checked (and placed) first.
            stapel.append(rest)
            stapel.append(aktuell)
    return out
