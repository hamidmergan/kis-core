"""The slide content: each field exactly once, invalid kinds fall back to bullets."""

import json

import pytest

from src.features.praesentation import folien, gliederung
from src.features.praesentation.schemas import OutlineRow, PraesentationParams, Slide

FORM_TEXT = {"ueberschrift": 6, "zwischentitel": [], "fliesstexte": [90], "bilder": 0,
             "body_kinds": ["bullets", "table", "chart"]}
FORM_BILD = {"ueberschrift": 6, "zwischentitel": [], "fliesstexte": [40], "bilder": 2,
             "body_kinds": ["bullets"]}
FORM_SPALTEN = {"ueberschrift": 6, "zwischentitel": [6, 6], "fliesstexte": [50, 50], "bilder": 0,
                "body_kinds": ["bullets"]}
ROWS = [OutlineRow(id="s2", role="text", title="A", gist="a"),
        OutlineRow(id="s3", role="text_mit_bild", title="B", gist="b")]
FORMEN = {"s2": FORM_TEXT, "s3": FORM_BILD}


def _raw(slides):
    return json.dumps({"slides": slides})


class TestPrompt:
    def test_beschreibt_jede_folie_mit_ihren_feldern(self):
        msgs = folien.build_messages("Q", PraesentationParams(notes=True), ROWS, FORMEN)
        user = msgs[1]["content"]
        assert "SLIDE s2 (role text)" in user and "body: up to 90 words, allowed kinds: bullets, table, chart" in user
        assert "SLIDE s3 (role text_mit_bild)" in user and "images: 2" in user and "notes: yes" in user

    def test_ohne_titel_soll_das_modell_die_ueberschrift_schreiben(self):
        """A slide added by instruction alone has no title yet, the model has to invent one."""
        rows = [OutlineRow(id="s2", role="text", title="", gist="vergleiche die beiden Verfahren")]
        user = folien.build_messages("Q", PraesentationParams(), rows, {"s2": FORM_TEXT})[1]["content"]
        assert "SLIDE s2 (role text): no title yet, write one" in user
        assert "vergleiche die beiden Verfahren" in user

    def test_spalten_werden_als_spalten_beschrieben(self):
        msgs = folien.build_messages("Q", PraesentationParams(), [OutlineRow(id="s4", role="zwei_spalten", title="C")],
                                     {"s4": FORM_SPALTEN})
        assert "columns: 2 fields with word limits 50, 50, each with a heading of up to 6 words" in msgs[1]["content"]


class TestParse:
    def test_stichpunkte_und_bilder(self):
        raw = _raw([{"id": "s2", "title": "A!", "body": {"kind": "bullets", "items": ["x", "y"]}},
                    {"id": "s3", "title": "B", "body": {"kind": "bullets", "items": ["z"]},
                     "images": [{"prompt": "a lab"}], "notes": "Sprich."}])
        s2, s3 = folien.parse_answer(raw, ROWS, FORMEN)
        assert s2.title == "A!" and s2.body.items == ["x", "y"] and s2.images == []
        assert [i.prompt for i in s3.images] == ["a lab", "B"] and s3.notes == "Sprich."

    def test_fehlende_folie_ist_unbrauchbar(self):
        with pytest.raises(gliederung.Unusable):
            folien.parse_answer(_raw([{"id": "s2", "title": "A"}]), ROWS, FORMEN)

    def test_tabelle_und_diagramm(self):
        raw = _raw([{"id": "s2", "title": "A", "body": {"kind": "table", "header": ["Jahr", "Wert"],
                                                        "rows": [["2020", "1"], ["2021", "2"]]}},
                    {"id": "s3", "title": "B", "body": {"kind": "chart", "chart_type": "pie",
                                                        "categories": ["a", "b"],
                                                        "series": [{"name": "s", "values": [1, "2"]}]}}])
        s2, s3 = folien.parse_answer(raw, ROWS, FORMEN)
        assert s2.body.kind == "table" and s2.body.rows == [["2020", "1"], ["2021", "2"]]
        assert s3.body.kind == "bullets"  # chart is not an allowed kind for s3

    def test_nicht_erlaubte_art_faellt_auf_stichpunkte(self):
        raw = _raw([{"id": "s2", "title": "A", "body": {"kind": "image", "prompt": "x", "items": ["p"]}},
                    {"id": "s3", "title": "B", "body": "nur Text"}])
        s2, s3 = folien.parse_answer(raw, ROWS, FORMEN)
        assert s2.body.kind == "bullets" and s2.body.items == ["p"]
        assert s3.body.kind == "bullets" and s3.body.items == ["nur Text"]

    def test_diagramm_ohne_werte_wird_stichpunkte(self):
        raw = _raw([{"id": "s2", "title": "A", "body": {"kind": "chart", "categories": [], "series": []}},
                    {"id": "s3", "title": "B"}])
        s2, _ = folien.parse_answer(raw, ROWS, FORMEN)
        assert s2.body.kind == "bullets"

    def test_spalten_werden_aufgefuellt(self):
        raw = _raw([{"id": "s4", "title": "C", "columns": [{"heading": "L", "items": ["1"]}]}])
        (s4,) = folien.parse_answer(raw, [OutlineRow(id="s4", role="zwei_spalten", title="C")], {"s4": FORM_SPALTEN})
        assert len(s4.columns) == 2 and s4.columns[0].heading == "L" and s4.columns[1].items == []

    def test_geschwister_folien_ausserhalb_von_slides_werden_gefunden(self):
        """A slide the model placed as a top-level sibling key, outside the "slides" array, is still picked up."""
        rows = [OutlineRow(id="s2", role="text", title="A"), OutlineRow(id="s3", role="text", title="B"),
                OutlineRow(id="s4", role="text", title="C")]
        formen = {r.id: FORM_TEXT for r in rows}
        raw = json.dumps({"slides": [{"id": "s2", "title": "A2"}],
                          "s3": {"id": "s3", "title": "B2"}, "s4": {"id": "s4", "title": "C2"}})
        s2, s3, s4 = folien.parse_answer(raw, rows, formen)
        assert [s.title for s in (s2, s3, s4)] == ["A2", "B2", "C2"]

    def test_doppelter_slides_schluessel_wird_zusammengefuehrt(self):
        """Two separate "slides" arrays under the same key are concatenated instead of the first being dropped."""
        rows = [OutlineRow(id="s2", role="text", title="A"), OutlineRow(id="s3", role="text", title="B"),
                OutlineRow(id="s4", role="text", title="C")]
        formen = {r.id: FORM_TEXT for r in rows}
        raw = ('{"slides": [{"id": "s2", "title": "A2"}], '
              '"slides": [{"id": "s3", "title": "B2"}, {"id": "s4", "title": "C2"}]}')
        s2, s3, s4 = folien.parse_answer(raw, rows, formen)
        assert [s.title for s in (s2, s3, s4)] == ["A2", "B2", "C2"]

    def test_saubere_form_parst_und_meldet_echte_luecke(self):
        """The plain shape still parses normally, and still raises Unusable when a row's id is genuinely missing."""
        rows = [OutlineRow(id="s2", role="text", title="A"), OutlineRow(id="s3", role="text", title="B")]
        formen = {r.id: FORM_TEXT for r in rows}
        s2, s3 = folien.parse_answer(_raw([{"id": "s2", "title": "A2"}, {"id": "s3", "title": "B2"}]), rows, formen)
        assert s2.title == "A2" and s3.title == "B2"
        with pytest.raises(gliederung.Unusable):
            folien.parse_answer(_raw([{"id": "s2", "title": "A2"}]), rows, formen)

    def test_verschachtelte_id_in_akzeptierter_folie_verdeckt_keine_echte_folie(self):
        """A nested id-bearing dict inside an already-accepted slide must not shadow a later real slide sharing that id."""
        rows = [OutlineRow(id="s2", role="text", title="A"), OutlineRow(id="s3", role="text", title="B")]
        formen = {r.id: FORM_TEXT for r in rows}
        raw = json.dumps({
            "slides": [{"id": "s2", "title": "A2",
                        "body": {"kind": "bullets", "items": ["x"], "extra": {"id": "s3", "title": "Falsch"}}}],
            "s3": {"id": "s3", "title": "Echte B"},
        })
        s2, s3 = folien.parse_answer(raw, rows, formen)
        assert s2.title == "A2"
        assert s3.title == "Echte B"

    def test_ohne_id_tragende_dicts_ist_unbrauchbar(self):
        """An answer with no id-bearing dict anywhere raises Unusable with the exact "no slides" message."""
        with pytest.raises(gliederung.Unusable, match="die Antwort enthält keine Folien"):
            folien.parse_answer(json.dumps({"foo": "bar", "baz": [1, 2, 3]}), ROWS, FORMEN)


class TestRegen:
    def test_regen_liefert_genau_zwei_nachrichten_mit_wunsch(self):
        row = ROWS[0]
        slide = Slide(id="s2", role="text", title="A")
        verlauf = [{"role": "user", "content": "kürzer"}]
        msgs = folien.regen_messages(slide, row, FORM_TEXT, PraesentationParams(), verlauf, "", "Q")
        assert len(msgs) == 2 and msgs[1]["role"] == "user"
        assert "WISH OF THE TEACHER: kürzer" in msgs[1]["content"]
        assert "CONVERSATION SO FAR:" not in msgs[1]["content"]

    def test_regen_mit_zwischenschritt_traegt_verlauf_und_letzten_wunsch(self):
        row = ROWS[0]
        slide = Slide(id="s2", role="text", title="A")
        verlauf = [{"role": "user", "content": "kürzer"}, {"role": "assistant", "content": "Ok, so"},
                   {"role": "user", "content": "noch kürzer"}]
        msgs = folien.regen_messages(slide, row, FORM_TEXT, PraesentationParams(), verlauf, "", "Q")
        content = msgs[1]["content"]
        assert len(msgs) == 2 and msgs[1]["role"] == "user"
        assert "CONVERSATION SO FAR:" in content and "assistant: Ok, so" in content
        assert "WISH OF THE TEACHER: noch kürzer" in content


def test_source_excerpt_findet_die_stelle():
    quelle = "Anfang. " * 50 + "Der Regelkreis hat vier Glieder." + " Ende." * 50
    assert "Regelkreis" in folien.source_excerpt(quelle, ["Regelkreis"], 200)


class TestSprechtext:
    """Notes were asked for, so an answer without them is unusable and gets asked again."""

    def test_fehlender_sprechtext_ist_unbrauchbar(self):
        raw = _raw([{"id": "s2", "title": "A", "body": {"kind": "bullets", "items": ["x"]}},
                    {"id": "s3", "title": "B", "notes": "Sprich."}])
        with pytest.raises(gliederung.Unusable):
            folien.parse_answer(raw, ROWS, FORMEN, True)

    def test_mit_sprechtext_geht_die_antwort_durch(self):
        raw = _raw([{"id": "s2", "title": "A", "notes": "Eins."}, {"id": "s3", "title": "B", "notes": "Zwei."}])
        s2, s3 = folien.parse_answer(raw, ROWS, FORMEN, True)
        assert s2.notes == "Eins." and s3.notes == "Zwei."

    def test_ohne_gewuenschte_notizen_stoert_der_leere_sprechtext_nicht(self):
        raw = _raw([{"id": "s2", "title": "A"}, {"id": "s3", "title": "B"}])
        assert [s.notes for s in folien.parse_answer(raw, ROWS, FORMEN)] == ["", ""]
