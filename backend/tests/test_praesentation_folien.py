"""The slide content: each field exactly once, invalid kinds fall back to bullets."""

import json

import pytest

from src.features.praesentation import folien, gliederung, icons
from src.features.praesentation.schemas import OutlineRow, PraesentationParams, Slide

FORM_TEXT = {"ueberschrift": 6, "zwischentitel": [], "fliesstexte": [90], "bilder": 0,
             "body_kinds": ["bullets", "table", "chart"]}
FORM_FORMEN = {"ueberschrift": 6, "zwischentitel": [], "fliesstexte": [90], "bilder": 0,
               "body_kinds": ["bullets", "table", "chart", "cards", "bars", "highlight"],
               "karten": {"max": 3, "titel_woerter": 4, "text_woerter": 15}, "balken": 4}
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


class TestFaktenJeFolie:
    """Ein Folienpaket sieht nur die Fakten seiner Zeilen, nicht mehr das ganze Material."""

    FAKTEN = {"s2": '#1 (Zahl) Es sind 40 Grad. Beleg: "40 Grad"',
              "s3": '#7 (These) Alles fliesst. Beleg: "panta rhei"'}




    def test_ohne_fakten_bleibt_alles_beim_alten(self):
        user = folien.build_messages("DAS GANZE MATERIAL", PraesentationParams(), ROWS,
                                     FORMEN)[1]["content"]
        assert user.startswith("MATERIAL:\nDAS GANZE MATERIAL")



class TestFaktenWaehlen:
    """Welche Fakten eine Zeile bekommt, und was eine Zeile ohne Nummern bekommt."""








# ── Material je Folie: Aussagen mit Beleg und die Passagen dazu ──────────────

class TestMaterialJeFolie:
    def _karte(self):
        from src.services.source_reading import Piece, Source
        from src.services.text_map import Karte

        # Weit genug auseinander, dass ein Nachbar das ferne Stueck nicht mitbringt.
        text = "AAAA BBBB CCCC DDDD EEEE"
        stuecke = [Piece(seite=1, von=i * 5, bis=i * 5 + 4) for i in range(5)]
        return Karte([Source(dateiname="a.pdf", fassung="x", text=text, seiten=1,
                             stuecke=stuecke)])

    def test_eine_folie_bekommt_ihre_stelle_aus_dem_original(self):
        zeilen = [OutlineRow(id="s1", stellen=[1])]
        aus = folien.material_je_folie(zeilen, self._karte(), zeilen)
        assert "AAAA" in aus["s1"] and "BBBB" in aus["s1"]

    def test_eine_ferne_stelle_kommt_nicht_mit(self):
        zeilen = [OutlineRow(id="s1", stellen=[1])]
        aus = folien.material_je_folie(zeilen, self._karte(), zeilen)
        assert "EEEE" not in aus["s1"]

    def test_die_stelle_nennt_datei_und_seite(self):
        zeilen = [OutlineRow(id="s1", stellen=[3])]
        aus = folien.material_je_folie(zeilen, self._karte(), zeilen)
        assert "[a.pdf, S. 1]" in aus["s1"]

    def test_eine_folie_ohne_stellen_bekommt_den_plan_des_decks(self):
        """Eine Agenda oder eine Schlussfolie nennt keine Stellen, das ist kein Fehler."""
        zeilen = [OutlineRow(id="s1", title="Agenda"),
                  OutlineRow(id="s2", title="Zulassung", gist="Wer zulaesst", stellen=[2])]
        aus = folien.material_je_folie(zeilen[:1], self._karte(), zeilen)
        assert "Zulassung: Wer zulaesst" in aus["s1"]
        assert "Agenda" not in aus["s1"]

    def test_mit_eigenem_material_faellt_der_gemeinsame_materialblock_weg(self):
        zeilen = [OutlineRow(id="s1", role="text", title="T", gist="g")]
        nachrichten = folien.build_messages("DER BLOCK", PraesentationParams(), zeilen,
                                            {"s1": FORM_TEXT}, {"s1": "Eigene Stelle"})
        user = nachrichten[1]["content"]
        assert "DER BLOCK" not in user
        assert "Eigene Stelle" in user
        assert "from its own material only" in nachrichten[0]["content"]


class TestWieNotebookLM:
    def test_aussagen_tragen_ihren_paragrafen(self):
        system = folien.build_messages("Q", PraesentationParams(), ROWS, FORMEN)[0]["content"]
        assert "name it in parentheses at the end of the statement" in system

    def test_eine_tabelle_darf_auch_vergleichen(self):
        system = folien.build_messages("Q", PraesentationParams(), ROWS, FORMEN)[0]["content"]
        assert "compared along the same attributes" in system

    def test_der_titel_nennt_seine_zeichengrenze(self):
        form = dict(FORM_TEXT, ueberschrift_zeichen=32)
        user = folien.build_messages("Q", PraesentationParams(), ROWS[:1], {"s2": form})[1]["content"]
        assert "title limit: 6 words, at most 32 characters" in user


class TestGenugPunkte:
    def test_stichpunkte_fuenf_bis_sieben(self):
        system = folien.build_messages("Q", PraesentationParams(), ROWS, FORMEN)[0]["content"]
        assert "with 5 to 7 short points" in system

    def test_jede_spalte_mindestens_drei(self):
        user = folien.build_messages("Q", PraesentationParams(), [OutlineRow(id="s4", role="zwei_spalten", title="C")],
                                     {"s4": FORM_SPALTEN})[1]["content"]
        assert "at least 3 points in each" in user

    def test_eine_tabelle_steht_allein(self):
        system = folien.build_messages("Q", PraesentationParams(), ROWS, FORMEN)[0]["content"]
        assert "A table stands alone" in system

    def test_neben_einer_tabelle_bleiben_keine_punkte(self):
        raw = _raw([{"id": "s2", "title": "A", "body": {"kind": "table", "header": ["a", "b"],
                                                        "rows": [["1", "2"]], "items": ["extra"]}}])
        s2, = folien.parse_answer(raw, ROWS[:1], FORMEN)
        assert s2.body.kind == "table" and s2.body.items == []


class TestZuDuenn:
    def test_ein_stichpunkt_ist_zu_duenn(self):
        s = Slide(id="s2", role="text", body={"kind": "bullets", "items": ["nur einer"]})
        assert folien.zu_duenn([s], {"s2": FORM_TEXT}) == {"s2": "1 bullet points, it needs 4 to 7"}

    def test_vier_stichpunkte_reichen(self):
        s = Slide(id="s2", role="text", body={"kind": "bullets", "items": ["a", "b", "c", "d"]})
        assert folien.zu_duenn([s], {"s2": FORM_TEXT}) == {}

    def test_ein_kleines_feld_verlangt_weniger(self):
        # 40 words carry about three points of twelve words, not four.
        s = Slide(id="s3", role="text_mit_bild", body={"kind": "bullets", "items": ["a", "b", "c"]})
        assert folien.zu_duenn([s], {"s3": FORM_BILD}) == {}

    def test_tabelle_und_karten_zaehlen_nicht(self):
        s = Slide(id="s2", role="text", body={"kind": "table", "header": ["a"], "rows": [["1"]]})
        assert folien.zu_duenn([s], {"s2": FORM_TEXT}) == {}

    def test_eine_duenne_spalte_macht_die_folie_duenn(self):
        s = Slide(id="s4", role="zwei_spalten", columns=[{"items": ["a", "b", "c"]}, {"items": ["a"]}])
        assert folien.zu_duenn([s], {"s4": FORM_SPALTEN}) == {"s4": "columns with 3, 1 points, each needs at least 3"}

    def test_nachfrage_nennt_die_duennen_folien_und_haengt_an(self):
        basis = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
        n = folien.nachfrage(basis, "ANTWORT", {"s2": "1 bullet points, it needs 4 to 7"})
        assert n[:2] == basis and n[2] == {"role": "assistant", "content": "ANTWORT"}
        assert "- s2: 1 bullet points" in n[3]["content"] and "never invented" in n[3]["content"]


class TestKartenVerteilen:
    def test_nur_jede_dritte_moegliche_folie_darf_karten(self):
        rows = [OutlineRow(id=f"s{i}", role="text", title="T") for i in range(1, 8)]
        formen = {r.id: FORM_FORMEN for r in rows}
        formen["s2"] = FORM_BILD  # a picture slide cannot carry cards and does not count
        assert folien.karten_folien(rows, formen) == {"s1", "s5"}

    def test_ohne_karten_nimmt_nur_die_karten_weg(self):
        assert folien.ohne_karten(FORM_FORMEN)["body_kinds"] == ["bullets", "table", "chart", "bars", "highlight"]
        assert "cards" in FORM_FORMEN["body_kinds"]

    def test_eine_folie_ohne_karten_bekommt_sie_nicht_angeboten(self):
        user = folien.build_messages("Q", PraesentationParams(), ROWS[:1], {"s2": folien.ohne_karten(FORM_FORMEN)})[1]["content"]
        assert "cards" not in user

    def test_verbotene_karten_werden_zu_stichpunkten(self):
        raw = _raw([{"id": "s2", "title": "A", "body": {"kind": "cards", "cards": [
            {"icon": "star", "title": "Leistung", "text": "Was geliefert wird."},
            {"icon": "clock", "title": "Termine", "text": "Bis wann."}]}}])
        s2, = folien.parse_answer(raw, ROWS[:1], {"s2": folien.ohne_karten(FORM_FORMEN)})
        assert s2.body.kind == "bullets" and s2.body.items == ["Leistung: Was geliefert wird.", "Termine: Bis wann."]


class TestBilderOhneSchrift:
    def test_bilder_sind_keine_diagramme_und_tragen_keine_schrift(self):
        system = folien.build_messages("Q", PraesentationParams(), ROWS, FORMEN)[0]["content"]
        assert "Never a diagram, chart, curve, formula" in system and "never words, labels" in system


class TestFormen:
    """Cards, bars and the highlight: parsed with their caps, anything too thin falls back to bullets."""

    ROW = [OutlineRow(id="s2", role="text", title="A")]

    def _body(self, body, form=FORM_FORMEN):
        return folien.parse_answer(_raw([{"id": "s2", "title": "A", "body": body}]), self.ROW, {"s2": form})[0].body

    def test_prompt_nennt_platz_und_icons(self):
        user = folien.build_messages("Q", PraesentationParams(), self.ROW, {"s2": FORM_FORMEN})
        assert "cards: 2 to 3, each title up to 4 words, each text up to 15 words" in user[1]["content"]
        assert "bars: 2 to 4" in user[1]["content"]
        assert "lightbulb" in user[0]["content"] and "highlight" in user[0]["content"]

    def test_karten_mit_ersatz_icon_und_deckel(self):
        karten = [{"icon": "lightbulb", "title": f"T{i}", "text": "x"} for i in range(5)]
        karten[1]["icon"] = "gibt-es-nicht"
        b = self._body({"kind": "cards", "cards": karten + [{"title": ""}]})
        assert b.kind == "cards" and len(b.cards) == 3
        assert [k.icon for k in b.cards] == ["lightbulb", icons.ERSATZ, "lightbulb"]

    def test_eine_karte_wird_stichpunkt(self):
        b = self._body({"kind": "cards", "cards": [{"icon": "x", "title": "Nur", "text": "eine"}]})
        assert b.kind == "bullets" and b.items == ["Nur: eine"] and b.cards == []

    def test_balken(self):
        b = self._body({"kind": "bars", "bars": [{"label": "A", "value": "2028", "text": "bis 2028"},
                                                  {"label": "B", "value": 3}, {"value": 9}]})
        assert b.kind == "bars" and [(z.label, z.value, z.text) for z in b.bars] == [
            ("A", 2028.0, "bis 2028"), ("B", 3.0, "")]

    def test_hervorhebung(self):
        b = self._body({"kind": "highlight", "key": "MO", "text": "Montags vor Ort.", "emphasis": "Montags"})
        assert (b.kind, b.key, b.text, b.emphasis) == ("highlight", "MO", "Montags vor Ort.", "Montags")

    def test_betonung_ausserhalb_des_satzes_faellt_weg(self):
        b = self._body({"kind": "highlight", "key": "12.500", "text": "Studierende nutzen es.", "emphasis": "dreimal"})
        assert b.kind == "highlight" and b.emphasis == ""

    def test_hervorhebung_ohne_satz_wird_stichpunkt(self):
        b = self._body({"kind": "highlight", "key": "MO"})
        assert b.kind == "bullets" and b.items == ["MO"] and b.key == ""

    def test_formen_nur_wo_erlaubt(self):
        b = self._body({"kind": "cards", "cards": [{"title": "a"}, {"title": "b"}]}, FORM_TEXT)
        assert b.kind == "bullets"
