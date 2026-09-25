"""Bullets for a list in a field whose layout switches them off, taken from the master's own body style."""

from __future__ import annotations

from copy import deepcopy

from lxml import etree

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_BU = ("buClrTx", "buClr", "buSzTx", "buSzPct", "buSzPts", "buFontTx", "buFont", "buNone", "buAutoNum",
       "buChar", "buBlip")
# What the stock Office master uses, for a master that names no bullet of its own.
_STANDARD_EINZUG = 228600


def ergaenze(ph) -> None:
    """Gives every paragraph of a list of two or more the master's bullet, when the layout shows none."""
    absaetze = ph.text_frame.paragraphs
    if len(absaetze) < 2 or not _ohne_zeichen(ph):
        return
    vorbild = _vorbild(ph)
    for absatz in absaetze:
        ppr = absatz._p.get_or_add_pPr()
        for kind in list(ppr):
            if etree.QName(kind).localname in _BU:
                ppr.remove(kind)
        ppr.set("marL", vorbild.get("marL", str(_STANDARD_EINZUG)))
        ppr.set("indent", vorbild.get("indent", str(-_STANDARD_EINZUG)))
        # Bullet elements come after spacing and before tabs and run defaults in the schema's order.
        stelle = next((i for i, k in enumerate(ppr) if etree.QName(k).localname in ("tabLst", "defRPr", "extLst")),
                      len(ppr))
        for i, kind in enumerate(k for k in vorbild if etree.QName(k).localname in _BU):
            ppr.insert(stelle + i, deepcopy(kind))


def _ohne_zeichen(ph) -> bool:
    layout_ph = next((p for p in ph.part.slide_layout.placeholders
                      if p.placeholder_format.idx == ph.placeholder_format.idx), None)
    if layout_ph is None:
        return False
    stufe = layout_ph._element.find(f".//{_A}lstStyle/{_A}lvl1pPr")
    return stufe is not None and stufe.find(f"{_A}buNone") is not None


def _vorbild(ph):
    """The master's first body level, or a plain round bullet when the master has none."""
    master = ph.part.slide_layout.slide_master._element
    stufe = master.find(f".//{_P}bodyStyle/{_A}lvl1pPr")
    if stufe is not None and stufe.find(f"{_A}buChar") is not None:
        return stufe
    ersatz = etree.Element(f"{_A}lvl1pPr", marL=str(_STANDARD_EINZUG), indent=str(-_STANDARD_EINZUG))
    etree.SubElement(ersatz, f"{_A}buFont", typeface="Arial")
    etree.SubElement(ersatz, f"{_A}buChar", char="•")
    return ersatz
