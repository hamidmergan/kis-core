"""Reads a template's first master and sorts its layouts into roles the model can pick."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from io import BytesIO

from lxml import etree
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from src.features.praesentation import raster
from src.features.praesentation.schemas import WAEHLBARE_ROLLEN

EMU_PER_INCH = 914400
EMU_PER_PT = 12700
RANDTEXT_PT = 12.0
FLIESSTEXT_MIN_HOEHE = EMU_PER_INCH
MAX_WORDS = {"ueberschrift": 10, "zwischentitel": 8, "fliesstext": 120}
_NICHT_BEFUELLT = {"DATE", "FOOTER", "SLIDE_NUMBER"}
_ABSCHLUSS = re.compile(r"abschluss|ende|danke|closing|thank", re.I)
_ABSCHNITT = re.compile(r"abschnitt|section", re.I)
_LVL1 = re.compile(r"<a:lvl1pPr(?:\s[^>]*[^/])?>(.*?)</a:lvl1pPr>", re.S)
_SZ = re.compile(r"\ssz=\"(\d+)\"")
_ANY_SZ = re.compile(r"<a:(?:defRPr|rPr|endParaRPr)[^>]*?\ssz=\"(\d+)\"")
_CAPS = re.compile(r"<a:(?:defRPr|rPr)[^>]*?\scap=\"all\"")
_BOLD = re.compile(r"<a:(?:defRPr|rPr)[^>]*?\sb=\"1\"")
_BODY_PR = re.compile(r"<a:bodyPr[^>]*>")
_INS = {"l": "lIns", "r": "rIns", "t": "tIns", "b": "bIns"}
# What PowerPoint uses when the shape names no inset of its own.
_INSET_H_STD = 91440
_INSET_V_STD = 45720


@dataclass
class Feld:
    idx: int
    art: str
    typ: str
    left: int
    top: int
    width: int
    height: int
    size_pt: float = 0.0
    is_object: bool = False
    words: int = 0
    # Long words overrun a word budget, a heading gets a character cap on top.
    chars: int = 0
    caps: bool = False
    bold: bool = False
    # Left plus right inset, and the one on the side the text is anchored to.
    inset_h: int = 2 * _INSET_H_STD
    inset_v: int = _INSET_V_STD
    # Where the text sits and how far it keeps from top and bottom, to find where a heading really ends.
    anker: str = "t"
    inset_oben: int = _INSET_V_STD
    inset_unten: int = _INSET_V_STD
    # A fixed line pitch the template sets, 0 when lines follow the font size.
    zeile_pt: float = 0.0

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0


@dataclass
class Layout:
    index: int
    name: str
    rolle: str | None
    felder: list[Feld] = field(default_factory=list)

    def der_art(self, art: str) -> list[Feld]:
        """Fields of one kind, left to right, then top to bottom."""
        return sorted((f for f in self.felder if f.art == art), key=lambda f: (f.left, f.top))


@dataclass
class Analyse:
    breite: int
    hoehe: int
    typeface: str
    layouts: list[Layout] = field(default_factory=list)
    rollen: dict[str, list[int]] = field(default_factory=dict)
    uebersprungen: list[str] = field(default_factory=list)

    def layout(self, index: int) -> Layout:
        return next(l for l in self.layouts if l.index == index)

    def hat_bildfelder(self) -> bool:
        return any(f.art == "bild" for l in self.layouts for f in l.felder)


def als_dict(a: Analyse) -> dict:
    return asdict(a)


def aus_dict(d: dict) -> Analyse:
    layouts = [Layout(index=l["index"], name=l["name"], rolle=l["rolle"],
                      felder=[Feld(**f) for f in l["felder"]]) for l in d["layouts"]]
    return Analyse(breite=d["breite"], hoehe=d["hoehe"], typeface=d["typeface"], layouts=layouts,
                   rollen={k: list(v) for k, v in d["rollen"].items()},
                   uebersprungen=list(d.get("uebersprungen", [])))


def analysiere(quelle: bytes | str) -> Analyse:
    prs = Presentation(BytesIO(quelle) if isinstance(quelle, bytes) else quelle)
    master = prs.slide_masters[0]
    titel_pt, text_pt = _master_grade(master)
    a = Analyse(breite=prs.slide_width, hoehe=prs.slide_height, typeface=_typeface(master))
    for i, layout in enumerate(master.slide_layouts):
        a.layouts.append(Layout(index=i, name=layout.name, rolle=None,
                                felder=_felder(layout, titel_pt, text_pt)))
    _rollen_zuordnen(a)
    return a


def waehlbare_rollen(a: Analyse) -> list[str]:
    return sorted(r for r in a.rollen if r in WAEHLBARE_ROLLEN)


def layout_fuer(a: Analyse, rolle: str, zaehler: dict[str, int]) -> Layout:
    """The next layout of the role, rotating so neighbours of one role look different."""
    kandidaten = a.rollen.get(rolle) or a.rollen.get("text") or [a.layouts[0].index]
    n = zaehler.get(rolle, 0)
    zaehler[rolle] = n + 1
    return a.layout(kandidaten[n % len(kandidaten)])


def form_fuer(l: Layout, a: Analyse) -> dict:
    """What the model has to fill for this layout, with the word limit of every field."""
    flies = l.der_art("fliesstext")
    arten = ["bullets"]
    platz: dict = {}
    # A table, chart or drawn element needs the whole slide, beside pictures it would be squeezed.
    if flies and flies[0].is_object and not l.der_art("bild"):
        arten += ["table", "chart", "cards", "bars", "highlight"]
        if not a.hat_bildfelder():
            arten.append("image")
        f = flies[0]
        platz = {"karten": raster.karten_platz(f.width, f.height, f.size_pt),
                 "balken": raster.balken_platz(f.height, f.size_pt)}
    return {
        **platz,
        "ueberschrift": next((f.words for f in l.der_art("ueberschrift")), 8),
        "ueberschrift_zeichen": next((f.chars for f in l.der_art("ueberschrift")), 0),
        "zwischentitel": [f.words for f in l.der_art("zwischentitel")],
        "fliesstexte": [f.words for f in flies],
        "bilder": len(l.der_art("bild")),
        "body_kinds": arten,
    }


def _xml(el) -> str:
    return etree.tostring(el).decode("utf8", "ignore")


def _eigener_schriftgrad(xml: str) -> float | None:
    lvl1 = _LVL1.search(xml)
    if lvl1:
        m = _SZ.search(lvl1.group(1))
        if m:
            return int(m.group(1)) / 100
    m = _ANY_SZ.search(xml)
    return int(m.group(1)) / 100 if m else None


def _schnitt(xml: str) -> tuple[bool, bool]:
    """Small caps and bold, both widen the text far beyond what its plain form measures."""
    return bool(_CAPS.search(xml)), bool(_BOLD.search(xml))


def _rahmen(xml: str) -> tuple[str, int, int]:
    """Anchor, top inset and bottom inset of the shape's text body."""
    tag = _BODY_PR.search(xml)
    if not tag:
        return "t", _INSET_V_STD, _INSET_V_STD
    anker = re.search(r'\sanchor="(\w+)"', tag.group(0))

    def wert(seite: str) -> int:
        m = re.search(rf'\s{_INS[seite]}="(\d+)"', tag.group(0))
        return int(m.group(1)) if m else _INSET_V_STD

    return (anker.group(1) if anker else "t"), wert("t"), wert("b")


def _zeilenabstand(xml: str) -> float:
    """A fixed line pitch in points from the first level's spacing, 0 when it is relative."""
    lvl1 = _LVL1.search(xml)
    m = re.search(r"<a:lnSpc>\s*<a:spcPts val=\"(\d+)\"", lvl1.group(1)) if lvl1 else None
    return int(m.group(1)) / 100 if m else 0.0


def _insets(xml: str) -> tuple[int, int]:
    """Left plus right inset, and the one the text is pushed away from by its anchor."""
    tag = _BODY_PR.search(xml)
    if not tag:
        return 2 * _INSET_H_STD, _INSET_V_STD

    def wert(seite: str, standard: int) -> int:
        m = re.search(rf'\s{_INS[seite]}="(\d+)"', tag.group(0))
        return int(m.group(1)) if m else standard

    anker = re.search(r'\sanchor="(\w+)"', tag.group(0))
    oben, unten = wert("t", _INSET_V_STD), wert("b", _INSET_V_STD)
    name = anker.group(1) if anker else "t"
    senkrecht = unten if name == "b" else oben + unten if name == "ctr" else oben
    return wert("l", _INSET_H_STD) + wert("r", _INSET_H_STD), senkrecht


def _master_grade(master) -> tuple[float, float]:
    xml = _xml(master._element)

    def stil(tag: str) -> float:
        m = re.search(rf"<p:{tag}>.*?<a:lvl1pPr[^>]*>.*?\ssz=\"(\d+)\"", xml, re.S)
        return int(m.group(1)) / 100 if m else 18.0

    return stil("titleStyle"), stil("bodyStyle")


def _typeface(master) -> str:
    try:
        theme = master.part.part_related_by(RT.THEME).blob.decode("utf8", "ignore")
    except Exception:
        return "Calibri"
    m = re.search(r"<a:minorFont>\s*<a:latin typeface=\"([^\"]+)\"", theme)
    return m.group(1) if m and not m.group(1).startswith("+") else "Calibri"


def _zeichenbudget(f: Feld) -> int:
    breite_pt = f.width / EMU_PER_PT - 36
    hoehe_pt = f.height / EMU_PER_PT - 7
    # Measured on Carlito: caps cost 17 percent width, bold another 2, and a budget
    # that ignores them lets the model write a title that wraps into the line below.
    breit = 0.5 * (1.17 if f.caps else 1.0) * (1.02 if f.bold else 1.0)
    zeichen_je_zeile = max(10.0, breite_pt / (f.size_pt * breit))
    zeilen = max(1, int(hoehe_pt / (f.size_pt * 1.2)))
    return int(zeichen_je_zeile * zeilen)


def _wortbudget(f: Feld) -> int:
    return max(2, min(MAX_WORDS.get(f.art, 120), int(_zeichenbudget(f) / 6.5)))


def _felder(layout, titel_pt: float, text_pt: float) -> list[Feld]:
    roh: list[Feld] = []
    for sh in layout.placeholders:
        pf = sh.placeholder_format
        typ = str(pf.type).split(" ")[0]
        if typ in _NICHT_BEFUELLT:
            continue
        if typ == "PICTURE":
            roh.append(Feld(pf.idx, "bild", typ, sh.left, sh.top, sh.width, sh.height))
            continue
        xml = _xml(sh._element)
        size = _eigener_schriftgrad(xml)
        if size is None:
            size = titel_pt if typ in ("TITLE", "CENTER_TITLE") else text_pt
        caps, bold = _schnitt(xml)
        inset_h, inset_v = _insets(xml)
        anker, inset_oben, inset_unten = _rahmen(xml)
        roh.append(Feld(pf.idx, "", typ, sh.left, sh.top, sh.width, sh.height,
                        size_pt=size, is_object=typ == "OBJECT", caps=caps, bold=bold,
                        inset_h=inset_h, inset_v=inset_v, anker=anker, inset_oben=inset_oben,
                        inset_unten=inset_unten, zeile_pt=_zeilenabstand(xml)))
    texte = [f for f in roh if f.art == ""]
    if texte:
        groesster = max(f.size_pt for f in texte)
        vergeben = False
        for f in texte:
            if not vergeben and f.size_pt == groesster:
                f.art, vergeben = "ueberschrift", True
            elif f.size_pt <= RANDTEXT_PT or f.size_pt <= text_pt * 0.75:
                f.art = "randtext"
            elif f.typ == "SUBTITLE":
                # A subtitle is as tall as a body in the stock Office master, only its type tells them apart.
                f.art = "zwischentitel"
            elif f.height >= FLIESSTEXT_MIN_HOEHE:
                f.art = "fliesstext"
            else:
                f.art = "zwischentitel"
            f.words = _wortbudget(f) if f.art != "randtext" else 0
            f.chars = _zeichenbudget(f) if f.art == "ueberschrift" else 0
    return roh


def _signatur(l: Layout) -> tuple:
    return tuple(sorted(f.art for f in l.felder))


def _rolle(l: Layout, erstes: Layout) -> str | None:
    arten = [f.art for f in l.felder]
    if l is erstes:
        return "deckblatt"
    if "ueberschrift" not in arten:
        return None
    if _ABSCHLUSS.search(l.name):
        return "abschluss"
    if _ABSCHNITT.search(l.name):
        return "abschnitt"
    if _signatur(l) == _signatur(erstes):
        return "deckblatt"
    f, b = arten.count("fliesstext"), arten.count("bild")
    if f == 0 and b == 0:
        return "abschnitt"
    if b == 0:
        return "text" if f == 1 else "zwei_spalten"
    return "text_mit_bild" if f else "bild_gross"


def _rollen_zuordnen(a: Analyse) -> None:
    if not a.layouts:
        return
    erstes = a.layouts[0]
    for l in a.layouts:
        l.rolle = _rolle(l, erstes)
        if l.rolle is None:
            a.uebersprungen.append(l.name)
        else:
            a.rollen.setdefault(l.rolle, []).append(l.index)
    if "abschluss" not in a.rollen:
        deckblaetter = a.rollen.get("deckblatt", [erstes.index])
        a.rollen["abschluss"] = [deckblaetter[1] if len(deckblaetter) > 1 else deckblaetter[0]]
