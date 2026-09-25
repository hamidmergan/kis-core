"""The one colour of a template and the tints every drawn element takes from it."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from src.features.praesentation.vorlage import Analyse

# The tints, as the share of the colour mixed onto white.
VOLL = 1.0
LINIE = 0.2
FLAECHE = 0.1
STREIFEN = 0.05
# Series and pie slices spread between these two shares, whatever their count.
STUFE_OBEN = 1.0
STUFE_UNTEN = 0.3
# Secondary text, the grey the AI notice already uses.
NEBENTEXT = "595959"
HILFSLINIE = "D9D9D9"
_ERSATZ = "404040"
# Below this saturation or outside these lightness bounds a colour reads as black, white or grey.
_MIN_SAETTIGUNG = 0.25
_MIN_HELL = 0.08
_MAX_HELL = 0.95
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_TITEL_TYPEN = ("title", "ctrTitle")
# WCAG's floor for large text, what a card title in the colour needs against its light card.
_MIN_TEXTKONTRAST = 3.0


@dataclass(frozen=True)
class Farben:
    """The template's colour in hex, and every tint the build asks for."""

    grund: str

    def ton(self, anteil: float) -> RGBColor:
        return RGBColor.from_string(mische(self.grund, anteil))

    def schrift_auf(self, anteil: float = VOLL) -> RGBColor:
        """Black or white, whichever stands out more on this tint."""
        return RGBColor.from_string(kontrastschrift(mische(self.grund, anteil)))

    def stufen(self, n: int) -> list[RGBColor]:
        return [self.ton(a) for a in stufen(n)]

    def textfarbe(self) -> RGBColor:
        """The colour itself for text on white or a light tint, black when it is too light to read there."""
        return RGBColor.from_string(self.grund if kontrast(self.grund, "FFFFFF") >= _MIN_TEXTKONTRAST else "000000")


def mische(hexwert: str, anteil: float) -> str:
    """The colour laid onto white at the given share, as a solid hex value."""
    r, g, b = (int(hexwert[i:i + 2], 16) for i in (0, 2, 4))
    return "".join(f"{round(c * anteil + 255 * (1 - anteil)):02X}" for c in (r, g, b))


def stufen(n: int) -> list[float]:
    """n shares evenly from full colour down to the lightest still readable one."""
    if n <= 1:
        return [STUFE_OBEN]
    schritt = (STUFE_OBEN - STUFE_UNTEN) / (n - 1)
    return [round(STUFE_OBEN - i * schritt, 4) for i in range(n)]


def _luminanz(hexwert: str) -> float:
    def kanal(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hexwert[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)


def kontrast(a: str, b: str) -> float:
    hell, dunkel = sorted((_luminanz(a), _luminanz(b)), reverse=True)
    return (hell + 0.05) / (dunkel + 0.05)


def kontrastschrift(hexwert: str) -> str:
    """WCAG contrast of black and of white against the colour, the higher one wins."""
    return "FFFFFF" if kontrast(hexwert, "FFFFFF") >= kontrast(hexwert, "000000") else "000000"


def unbunt(hexwert: str) -> bool:
    r, g, b = (int(hexwert[i:i + 2], 16) / 255 for i in (0, 2, 4))
    _, hell, saettigung = colorsys.rgb_to_hls(r, g, b)
    return saettigung < _MIN_SAETTIGUNG or hell < _MIN_HELL or hell > _MAX_HELL


def aus_vorlage(prs, a: Analyse) -> Farben:
    """The title colour of the content layout, else the second dark colour, else the first accent."""
    master = prs.slide_masters[0]
    schema = _farbschema(master)
    zuordnung = _zuordnung(master)
    kandidaten = [_titelfarbe(master, _inhaltslayout(prs, a), schema, zuordnung),
                  schema.get("dk2"), schema.get("accent1")]
    for farbe in kandidaten:
        if farbe and not unbunt(farbe):
            return Farben(farbe)
    return Farben(schema.get("accent1") or _ERSATZ)


def _inhaltslayout(prs, a: Analyse):
    for rolle in ("text", "zwei_spalten", "text_mit_bild"):
        if a.rollen.get(rolle):
            return prs.slide_masters[0].slide_layouts[a.rollen[rolle][0]]
    return None


def _farbschema(master) -> dict[str, str]:
    try:
        theme = etree.fromstring(master.part.part_related_by(RT.THEME).blob)
    except Exception:
        return {}
    schema = theme.find(f".//{_A}clrScheme")
    if schema is None:
        return {}
    werte: dict[str, str] = {}
    for eintrag in schema:
        name = etree.QName(eintrag).localname
        farbe = next(iter(eintrag), None)
        if farbe is None:
            continue
        wert = farbe.get("lastClr") if etree.QName(farbe).localname == "sysClr" else farbe.get("val")
        if wert and re.fullmatch(r"[0-9A-Fa-f]{6}", wert):
            werte[name] = wert.upper()
    return werte


def _zuordnung(master) -> dict[str, str]:
    """bg1, tx1 and the like as the master maps them onto the theme's dk1, lt1 and so on."""
    el = master._element.find(f"{_P}clrMap")
    standard = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}
    return {**standard, **dict(el.attrib)} if el is not None else standard


def _titelfarbe(master, layout, schema: dict[str, str], zuordnung: dict[str, str]) -> str | None:
    """The colour the title text really shows: the layout's own, else the master's title style."""
    if layout is not None:
        for sp in layout._element.iter(f"{_P}sp"):
            ph = sp.find(f".//{_P}ph")
            if ph is not None and ph.get("type") in _TITEL_TYPEN:
                koerper = sp.find(f"{_P}txBody")
                fuellung = koerper.find(f".//{_A}solidFill") if koerper is not None else None
                if fuellung is not None:
                    return _farbwert(fuellung, schema, zuordnung)
    stil = master._element.find(f".//{_P}titleStyle/{_A}lvl1pPr")
    fuellung = stil.find(f".//{_A}solidFill") if stil is not None else None
    return _farbwert(fuellung, schema, zuordnung) if fuellung is not None else None


def _farbwert(fuellung, schema: dict[str, str], zuordnung: dict[str, str]) -> str | None:
    farbe = next(iter(fuellung), None)
    if farbe is None:
        return None
    art = etree.QName(farbe).localname
    if art == "srgbClr":
        wert = (farbe.get("val") or "").upper()
    elif art == "sysClr":
        wert = (farbe.get("lastClr") or "").upper()
    elif art == "schemeClr":
        name = farbe.get("val") or ""
        wert = schema.get(zuordnung.get(name, name), "")
    else:
        return None
    if not re.fullmatch(r"[0-9A-F]{6}", wert):
        return None
    return _helligkeit(wert, farbe)


def _helligkeit(wert: str, farbe) -> str:
    """lumMod and lumOff, the two changes a theme colour usually carries in a title style."""
    mod = farbe.find(f"{_A}lumMod")
    off = farbe.find(f"{_A}lumOff")
    if mod is None and off is None:
        return wert
    r, g, b = (int(wert[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (int(mod.get("val")) / 100000 if mod is not None else 1) + (
        int(off.get("val")) / 100000 if off is not None else 0)
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), s)
    return "".join(f"{round(c * 255):02X}" for c in (r, g, b))
