"""The analysis of a template: field kinds by font size, roles by fields."""

from io import BytesIO
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from src.features.praesentation import vorlage

THL = Path("src/features/praesentation/assets/thl.pptx")


@pytest.fixture(scope="module")
def thl():
    return vorlage.analysiere(THL.read_bytes())


def _namen(a, rolle):
    return [a.layout(i).name for i in a.rollen.get(rolle, [])]


class TestThl:
    def test_einundfuenfzig_layouts_und_16_zu_9(self, thl):
        assert len(thl.layouts) == 51
        assert round(thl.breite / thl.hoehe, 2) == 1.78

    def test_ueberschrift_ist_das_grosse_textfeld_und_nicht_der_titel_platzhalter(self, thl):
        l = next(l for l in thl.layouts if l.name == "Text oder Grafik")
        ueber = l.der_art("ueberschrift")
        assert len(ueber) == 1 and ueber[0].typ == "BODY" and ueber[0].size_pt == 32
        rand = l.der_art("randtext")
        assert {f.typ for f in rand} == {"TITLE", "BODY"}
        assert all(f.size_pt == 11 for f in rand)

    def test_rollen(self, thl):
        assert _namen(thl, "deckblatt") == ["Titelfolie 1", "Titelfolie 2"]
        assert _namen(thl, "text")[0] == "Text oder Grafik"
        assert _namen(thl, "zwei_spalten")[0] == "Zwei Inhalte"
        assert _namen(thl, "abschnitt")[0] == "Abschnitt"
        assert _namen(thl, "bild_gross")[0] == "Großes Bild"
        assert _namen(thl, "abschluss") == ["Titelfolie 2"]
        assert thl.uebersprungen == []

    def test_die_alten_layouts_behalten_ihre_nummer(self, thl):
        alt = ["Titelfolie 1", "Titelfolie 2", "Text und Bilder", "Text oder Grafik", "Bilder mit Text", "Zwei Inhalte"]
        assert [thl.layout(i).name for i in range(6)] == alt

    def test_rotation_bringt_erst_die_layouts_mit_weniger_bildern(self, thl):
        bilder = [len(thl.layout(i).der_art("bild")) for i in thl.rollen["text_mit_bild"]]
        assert bilder == sorted(bilder) and bilder[0] == 1
        namen = _namen(thl, "text_mit_bild")
        assert namen.index("Text und Bild") < namen.index("Text und Bilder")

    def test_deckblatt_hat_untertitel_und_bannerbild(self, thl):
        l = thl.layout(0)
        assert l.der_art("zwischentitel")[0].size_pt == 20
        assert round(l.der_art("bild")[0].aspect, 1) == 3.8

    def test_zwei_spalten_hat_zwei_zwischentitel_und_zwei_fliesstexte(self, thl):
        l = next(l for l in thl.layouts if l.name == "Zwei Inhalte")
        assert len(l.der_art("zwischentitel")) == 2
        flies = l.der_art("fliesstext")
        assert len(flies) == 2 and flies[0].left < flies[1].left and all(f.is_object for f in flies)

    def test_wortbudget_ist_gedeckelt(self, thl):
        l = next(l for l in thl.layouts if l.name == "Text oder Grafik")
        assert l.der_art("fliesstext")[0].words == 120
        assert 4 <= l.der_art("ueberschrift")[0].words <= 10

    def test_typeface_kommt_aus_dem_thema(self, thl):
        # The real thl.pptx theme's minorFont latin typeface is "Calibri", not "Arial" (which only labels bullet characters).
        assert thl.typeface == "Calibri"

    def test_waehlbare_rollen(self, thl):
        assert vorlage.waehlbare_rollen(thl) == ["abschnitt", "bild_gross", "text", "text_mit_bild", "zwei_spalten"]

    def test_rundreise_als_dict(self, thl):
        assert vorlage.als_dict(vorlage.aus_dict(vorlage.als_dict(thl))) == vorlage.als_dict(thl)

    def test_form_fuer_text_layout_erlaubt_tabelle_diagramm_und_formen_aber_kein_bild(self, thl):
        l = next(l for l in thl.layouts if l.name == "Text oder Grafik")
        form = vorlage.form_fuer(l, thl)
        assert form["fliesstexte"] == [120] and form["bilder"] == 0
        assert form["body_kinds"] == ["bullets", "table", "chart", "cards", "bars", "highlight",
                                      "steps", "figures", "levels", "symbols"]
        assert form["karten"]["max"] == 6 and form["balken"] == 8
        assert form["schritte"]["max"] == 6 and form["kennzahlen"] == 4
        assert form["stufen"]["max"] == 5 and form["symbole"] == 8

    def test_folien_mit_bildfeld_bekommen_keine_tabelle(self, thl):
        for name in ("Text und Bilder", "Bilder mit Text"):
            l = next(l for l in thl.layouts if l.name == name)
            form = vorlage.form_fuer(l, thl)
            assert form["body_kinds"] == ["bullets"] and "karten" not in form


def _kuenstlich(layout_namen: list[tuple[str, list[str]]]) -> bytes:
    """A template built from python-pptx's default master, layouts renamed and reduced to placeholders by type."""
    prs = Presentation()
    master = prs.slide_masters[0]
    for layout, (name, _) in zip(master.slide_layouts, layout_namen):
        layout.name = name
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


class TestKuenstlich:
    def test_erstes_layout_ist_immer_deckblatt(self):
        a = vorlage.analysiere(_kuenstlich([("Irgendwas", [])]))
        assert a.layout(0).rolle == "deckblatt"

    def test_layoutname_abschluss_wird_erkannt(self):
        a = vorlage.analysiere(_kuenstlich([("Titel", []), ("Danke und Ende", [])]))
        assert a.layout(1).rolle == "abschluss"

    def test_layout_ohne_ueberschrift_wird_uebersprungen(self):
        prs = Presentation()
        leer = prs.slide_masters[0].slide_layouts[6]  # "Blank" in the default template
        a = vorlage.analysiere(_kuenstlich([("Titel", [])]))
        assert leer.name in a.uebersprungen or a.layout(6).rolle is None

    def test_layout_fuer_wechselt_bei_mehreren_kandidaten_durch(self):
        a = vorlage.analysiere(THL.read_bytes())
        z: dict[str, int] = {}
        erst = vorlage.layout_fuer(a, "text_mit_bild", z).name
        zweit = vorlage.layout_fuer(a, "text_mit_bild", z).name
        dritt = vorlage.layout_fuer(a, "text_mit_bild", z).name
        assert (erst, zweit, dritt) == ("Text und Bild", "Bild und Text", "Bild oben und Text")

    def test_unbekannte_rolle_faellt_auf_text(self):
        a = vorlage.analysiere(THL.read_bytes())
        assert vorlage.layout_fuer(a, "gibt_es_nicht", {}).name == "Text oder Grafik"


@pytest.fixture(scope="module")
def standard():
    """The stock Office master a normal deck carries, straight from python-pptx."""
    prs = Presentation()
    out = BytesIO()
    prs.save(out)
    return vorlage.analysiere(out.getvalue())


class TestOfficeStandard:
    def test_untertitel_ist_zwischentitel(self, standard):
        l = next(l for l in standard.layouts if l.name == "Title Slide")
        assert [f.typ for f in l.der_art("zwischentitel")] == ["SUBTITLE"]
        assert not l.der_art("fliesstext")

    def test_titel_und_inhalt_ist_text_und_kein_zweites_deckblatt(self, standard):
        l = next(l for l in standard.layouts if l.name == "Title and Content")
        assert l.rolle == "text"

    def test_text_steht_als_rolle_zur_wahl(self, standard):
        assert "text" in vorlage.waehlbare_rollen(standard)


def test_ein_titel_bekommt_auch_eine_zeichengrenze(thl):
    # One line of 44 pt caps across the cover: long German words need a character cap, not only words.
    deckblatt = thl.layout(0)
    zeichen = deckblatt.der_art("ueberschrift")[0].chars
    assert 25 <= zeichen <= 40
    assert vorlage.form_fuer(deckblatt, thl)["ueberschrift_zeichen"] == zeichen
