"""The one colour of a template: the content title, else the second dark colour, else the first accent."""

import os
from io import BytesIO
from pathlib import Path

import pptx
import pytest
from lxml import etree
from pptx import Presentation

from src.features.praesentation import farben, vorlage

THL = Path("src/features/praesentation/assets/thl.pptx").read_bytes()
STANDARD = Path(os.path.dirname(pptx.__file__), "templates", "default.pptx").read_bytes()
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def _aus(data: bytes) -> farben.Farben:
    return farben.aus_vorlage(Presentation(BytesIO(data)), vorlage.analysiere(data))


def _umgebaut(titel: str | None = None, dk2: str | None = None, mod: str | None = None) -> bytes:
    """The stock template with its master title colour or its second dark colour replaced."""
    prs = Presentation(BytesIO(STANDARD))
    master = prs.slide_masters[0]
    if titel is not None:
        fuellung = master._element.find(f".//{_P}titleStyle/{_A}lvl1pPr").find(f".//{_A}solidFill")
        for c in list(fuellung):
            fuellung.remove(c)
        farbe = etree.SubElement(fuellung, _A + ("schemeClr" if titel == "tx2" else "srgbClr"))
        farbe.set("val", titel)
        if mod:
            etree.SubElement(farbe, _A + "lumMod").set("val", mod)
    if dk2 is not None:
        theme_part = master.part.part_related_by(pptx.opc.constants.RELATIONSHIP_TYPE.THEME)
        theme = etree.fromstring(theme_part.blob)
        theme.find(f".//{_A}dk2")[0].set("val", dk2)
        theme_part._blob = etree.tostring(theme)
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def test_thl_schwarze_inhaltstitel_fuehren_zum_rot():
    """THL's content titles inherit black from the master, so the second dark colour steps in."""
    assert _aus(THL).grund == "E4003A"


def test_bunte_titelfarbe_gewinnt():
    assert _aus(_umgebaut(titel="2E8B57")).grund == "2E8B57"


def test_titel_als_themenfarbe_wird_ueber_die_zuordnung_aufgeloest():
    assert _aus(_umgebaut(titel="tx2")).grund == "1F497D"


def test_helligkeitsaenderung_wird_angewandt():
    grund = _aus(_umgebaut(titel="tx2", mod="50000")).grund
    assert grund != "1F497D" and farben._luminanz(grund) < farben._luminanz("1F497D")


def test_graue_zweitfarbe_faellt_auf_die_akzentfarbe():
    assert _aus(_umgebaut(dk2="44546A")).grund == "4F81BD"


def test_mische_auf_weiss():
    assert farben.mische("E4003A", 1.0) == "E4003A"
    assert farben.mische("E4003A", 0.0) == "FFFFFF"
    assert farben.mische("E4003A", 0.1) == "FCE6EB"


@pytest.mark.parametrize("n,erwartet", [(1, [1.0]), (2, [1.0, 0.3]), (4, [1.0, 0.7667, 0.5333, 0.3])])
def test_stufen_verteilen_sich_gleichmaessig(n, erwartet):
    assert farben.stufen(n) == erwartet


def test_kontrastschrift():
    assert farben.kontrastschrift("E4003A") == "FFFFFF"
    assert farben.kontrastschrift("1F497D") == "FFFFFF"
    assert farben.kontrastschrift("FFC000") == "000000"


def test_textfarbe_ist_schwarz_wenn_die_farbe_auf_weiss_zu_hell_ist():
    assert str(farben.Farben("E4003A").textfarbe()) == "E4003A"
    assert str(farben.Farben("FFC000").textfarbe()) == "000000"


@pytest.mark.parametrize("farbe,erwartet", [("000000", True), ("FFFFFF", True), ("808080", True),
                                            ("44546A", True), ("E4003A", False), ("1F497D", False)])
def test_unbunt(farbe, erwartet):
    assert farben.unbunt(farbe) is erwartet
