"""Bullet points that would not fit their field move to a second slide, never shrink."""

import pytest

from src.features.praesentation import teilung
from src.features.praesentation.schemas import MAX_TEXT_ITEMS, Body, Column, Slide
from src.features.praesentation.vorlage import EMU_PER_PT, Analyse, Feld, Layout


class _Font:
    """Every character six points wide, so the arithmetic is readable."""

    def getlength(self, text):
        return 6.0 * len(text)


@pytest.fixture(autouse=True)
def font(monkeypatch):
    monkeypatch.setattr(teilung, "_load_font", lambda typeface, size: _Font())


def _feld(idx, breite_pt, hoehe_pt, art="fliesstext"):
    return Feld(idx, art, "OBJECT", 0, 0, int(breite_pt * EMU_PER_PT), int(hoehe_pt * EMU_PER_PT),
                size_pt=16, is_object=True)


def _analyse():
    klein = Layout(1, "Klein", "text", [_feld(0, 40, 4, "ueberschrift"), _feld(2, 300, 80)])
    gross = Layout(2, "Gross", "text", [_feld(0, 40, 4, "ueberschrift"), _feld(2, 600, 200)])
    spalten = Layout(3, "Spalten", "zwei_spalten",
                     [_feld(0, 40, 4, "ueberschrift"), _feld(2, 200, 60), _feld(4, 200, 60)])
    return Analyse(breite=1, hoehe=1, typeface="Arial", layouts=[klein, gross, spalten],
                   rollen={"text": [1, 2], "zwei_spalten": [3]})


def test_kurze_punkte_passen():
    assert teilung.passt(["kurz", "auch kurz"], _feld(2, 300, 80), "Arial")


def test_viele_zeilen_passen_nicht():
    # 80 pt high field minus 7 pt inset leaves room for three 19.2 pt lines, four points need four.
    assert not teilung.passt(["a", "b", "c", "d"], _feld(2, 300, 80), "Arial")


def test_langer_punkt_bricht_um():
    breit = "wort " * 30
    assert teilung.zeilen([breit.strip()], _Font(), 100) > 1


def test_teilt_gegen_das_engste_feld_der_rolle():
    s = Slide(id="s3", role="text", title="T", body=Body(items=["a", "b", "c", "d", "e", "f"]))
    out = teilung.teile_ueberlauf([s], _analyse())
    assert [x.id for x in out] == ["s3", "s4"]
    assert out[0].body.items == ["a", "b", "c"] and out[1].body.items == ["d", "e", "f"]
    assert out[1].title == "T" and out[1].images == [] and out[1].role == "text"


def test_passende_folie_bleibt_ganz():
    s = Slide(id="s3", role="text", title="T", body=Body(items=["a", "b"]))
    assert len(teilung.teile_ueberlauf([s], _analyse())) == 1


def test_spalten_werden_beide_halbiert():
    s = Slide(id="s5", role="zwei_spalten", title="T",
              columns=[Column(heading="L", items=["1", "2", "3", "4"]), Column(heading="R", items=["a", "b"])])
    out = teilung.teile_ueberlauf([s], _analyse())
    assert len(out) == 2
    assert out[0].columns[0].items == ["1", "2"] and out[1].columns[0].items == ["3", "4"]
    assert out[1].columns[1].heading == "R" and out[1].columns[1].items == ["b"]


def test_ein_einzelner_punkt_wird_nie_geteilt():
    s = Slide(id="s3", role="text", title="T", body=Body(items=["x " * 400]))
    assert len(teilung.teile_ueberlauf([s], _analyse())) == 1


def test_neue_ids_zaehlen_hinter_der_hoechsten():
    a = Slide(id="s9", role="text", title="T", body=Body(items=["a", "b", "c", "d"]))
    b = Slide(id="s2", role="text", title="U", body=Body(items=["a"]))
    assert [x.id for x in teilung.teile_ueberlauf([a, b], _analyse())] == ["s9", "s10", "s2"]


def test_starker_ueberlauf_wird_so_oft_geteilt_bis_alles_passt():
    # As many points as a saved slide is ever allowed to carry, the schema cap in Body.items.
    items = [f"p{i}" for i in range(MAX_TEXT_ITEMS)]
    s = Slide(id="s3", role="text", title="T", body=Body(items=list(items)))
    out = teilung.teile_ueberlauf([s], _analyse())
    assert len(out) > 1
    assert all(len(o.body.items) <= 3 for o in out)
    assert [i for o in out for i in o.body.items] == items
    assert len({o.id for o in out}) == len(out)
    assert out[0].id == "s3"


def test_die_zweite_haelfte_behaelt_den_sprechtext():
    """No slide may end up without speaker text, and a split creates slides."""
    s = Slide(id="s3", role="text", title="T", notes="So spreche ich dazu.",
              body=Body(items=["a", "b", "c", "d", "e", "f"]))
    out = teilung.teile_ueberlauf([s], _analyse())
    assert len(out) == 2
    assert all(o.notes == "So spreche ich dazu." for o in out)


def test_auch_geteilte_spalten_behalten_den_sprechtext():
    s = Slide(id="s5", role="zwei_spalten", title="T", notes="So spreche ich dazu.",
              columns=[Column(heading="L", items=["1", "2", "3", "4"]), Column(heading="R", items=["a", "b"])])
    out = teilung.teile_ueberlauf([s], _analyse())
    assert len(out) == 2 and all(o.notes for o in out)


def test_eine_folie_mit_layout_misst_gegen_ihr_eigenes_feld():
    # Six short points fit the large field of layout 2, the small one of layout 1 is not this slide's.
    s = Slide(id="s3", role="text", layout=2, title="T", body=Body(items=["a", "b", "c", "d", "e", "f"]))
    assert len(teilung.teile_ueberlauf([s], _analyse())) == 1


def test_auch_im_eigenen_feld_wird_geteilt_was_nicht_passt():
    s = Slide(id="s3", role="text", layout=1, title="T", body=Body(items=["a", "b", "c", "d", "e", "f"]))
    assert len(teilung.teile_ueberlauf([s], _analyse())) == 2


def _mit_bild():
    a = _analyse()
    bild = Layout(4, "Bild", "text_mit_bild",
                  [_feld(0, 40, 4, "ueberschrift"), _feld(2, 300, 80), _feld(5, 100, 100, "bild")])
    a.layouts.append(bild)
    a.rollen["text_mit_bild"] = [4]
    return a


def test_der_rest_einer_bildfolie_wird_eine_textfolie():
    s = Slide(id="s3", role="text_mit_bild", layout=4, title="T",
              body=Body(items=["a", "b", "c", "d", "e", "f"]))
    out = teilung.teile_ueberlauf([s], _mit_bild())
    assert [o.role for o in out] == ["text_mit_bild", "text"]
    assert out[1].layout in (1, 2) and out[1].images == []
