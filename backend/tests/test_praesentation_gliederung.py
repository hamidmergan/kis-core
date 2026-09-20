"""The outline: what the model must deliver and what the rules make of it."""

import json

import pytest

from src.features.praesentation import gliederung
from src.features.praesentation.schemas import Outline, OutlineRow, PraesentationParams

ROLLEN = ["text", "text_mit_bild", "zwei_spalten"]


def _antwort(rollen, title="Deck"):
    return json.dumps({"title": title, "subtitle": "U", "slides": [
        {"role": r, "title": f"T{i}", "gist": f"G{i}"} for i, r in enumerate(rollen)]})


class TestPrompt:
    def test_nennt_spanne_rollen_und_sprache(self):
        msgs = gliederung.build_messages("Quelle", PraesentationParams(language="en"), ROLLEN)
        system = msgs[0]["content"]
        assert "Decide yourself how many slides" in system and "English" in system
        assert "at least 3 and at most 30 slides" in system
        assert "- zwei_spalten:" in system and "- abschnitt:" not in system
        assert msgs[1]["content"].startswith("MATERIAL:\nQuelle")

    def test_anweisung_kommt_ans_ende(self):
        msgs = gliederung.build_messages("Q", PraesentationParams(instructions="nur Kapitel 2"), ROLLEN)
        assert msgs[1]["content"].rstrip().endswith("nur Kapitel 2")


class TestParse:
    def test_liest_zaun_und_vergibt_ids(self):
        raw = "```json\n" + _antwort(["x", "text", "text_mit_bild", "text", "text", "x"]) + "\n```"
        o = gliederung.parse_answer(raw, ROLLEN)
        assert [r.id for r in o.rows] == ["s1", "s2", "s3", "s4", "s5", "s6"]
        assert o.title == "Deck" and o.subtitle == "U"

    def test_erzwingt_deckblatt_und_abschluss(self):
        o = gliederung.parse_answer(_antwort(["text"] * 6), ROLLEN)
        assert o.rows[0].role == "deckblatt" and o.rows[-1].role == "abschluss"

    def test_unbekannte_rolle_wird_text(self):
        o = gliederung.parse_answer(_antwort(["text", "quatsch", "text", "text", "text", "text"]), ROLLEN)
        assert o.rows[1].role == "text"

    def test_gleiche_rolle_hintereinander_wird_umgebogen(self):
        o = gliederung.parse_answer(
            _antwort(["d", "text_mit_bild", "text_mit_bild", "text", "text", "a"]), ROLLEN)
        assert [r.role for r in o.rows[1:5]] == ["text_mit_bild", "zwei_spalten", "text", "text"]

    def test_zu_wenige_folien_sind_unbrauchbar(self):
        with pytest.raises(gliederung.Unusable):
            gliederung.parse_answer(_antwort(["text"] * 2), ROLLEN)

    def test_das_modell_bestimmt_die_zahl_selbst(self):
        """Anything from the floor up to the cap is taken as it comes."""
        for n in (3, 12, 30):
            assert len(gliederung.parse_answer(_antwort(["text"] * n), ROLLEN).rows) == n

    def test_zu_viele_werden_hinten_gekuerzt(self):
        o = gliederung.parse_answer(_antwort(["text"] * 34), ROLLEN)
        assert len(o.rows) == 30 and o.rows[-1].role == "abschluss"

    def test_kein_json_ist_unbrauchbar(self):
        with pytest.raises(gliederung.Unusable):
            gliederung.parse_answer("Hier ist die Gliederung: 1. Einleitung", ROLLEN)


class TestJsonObjekt:
    def test_doppelter_schluessel_mit_listen_wird_zusammengefuehrt(self):
        """Two occurrences of the same key with list values are concatenated instead of the first being dropped."""
        assert gliederung.json_objekt('{"a": [1, 2], "a": [3]}') == {"a": [1, 2, 3]}


class TestIds:
    def test_behaelt_vorhandene_ids_und_ergaenzt_neue(self):
        rows = gliederung.mit_ids([OutlineRow(id="s4", title="a"), OutlineRow(id="", title="b"),
                                   OutlineRow(id="neu1", title="c")])
        assert [r.id for r in rows] == ["s4", "s5", "s6"]

    def test_loest_doppelte_auf(self):
        rows = gliederung.mit_ids([OutlineRow(id="s1", title="a"), OutlineRow(id="s1", title="b")])
        assert [r.id for r in rows] == ["s1", "s2"]


class TestRegen:
    def test_regen_liefert_titel_und_satz(self):
        title, gist = gliederung.parse_row('{"title": "Neu", "gist": "Anders"}')
        assert (title, gist) == ("Neu", "Anders")

    def test_regen_prompt_traegt_verlauf(self):
        o = Outline(rows=[OutlineRow(id="s1", role="text", title="A", gist="a")])
        msgs = gliederung.regen_messages(o.rows[0], o, PraesentationParams(), [{"role": "user", "content": "kürzer"}], "Q")
        assert len(msgs) == 2 and msgs[1]["role"] == "user"
        assert "[text] A: a" in msgs[1]["content"] and "kürzer" in msgs[1]["content"]

    def test_regen_prompt_mit_zwischenschritt(self):
        o = Outline(rows=[OutlineRow(id="s1", role="text", title="A", gist="a")])
        verlauf = [{"role": "user", "content": "kürzer"}, {"role": "assistant", "content": "Ok, so"},
                   {"role": "user", "content": "noch kürzer"}]
        msgs = gliederung.regen_messages(o.rows[0], o, PraesentationParams(), verlauf, "Q")
        content = msgs[1]["content"]
        assert "assistant: Ok, so" in content and "WISH OF THE TEACHER: noch kürzer" in content


def _antwort_mit_nummern(paare, title="Deck"):
    """Je Folie eine Rolle und die Faktennummern, auf die sie sich stuetzt."""
    return json.dumps({"title": title, "subtitle": "U", "slides": [
        {"role": r, "title": f"T{i}", "gist": f"G{i}", "fact_ids": ids}
        for i, (r, ids) in enumerate(paare)]})


class TestFaktennummern:
    """Die Gliederung zeigt auf den Vorrat, damit jede Folie nur ihre Fakten sieht."""

    def test_der_prompt_verlangt_nummern_wenn_ein_vorrat_da_ist(self):
        msgs = gliederung.build_messages("#1 (These) Alles fliesst", PraesentationParams(),
                                         ROLLEN, mit_nummern=True)
        assert "fact_ids" in msgs[0]["content"]
        assert msgs[1]["content"].startswith("FACTS:\n#1")

    def test_ohne_vorrat_bleibt_der_prompt_wie_bisher(self):
        msgs = gliederung.build_messages("Quelle", PraesentationParams(), ROLLEN)
        assert "fact_ids" not in msgs[0]["content"]
        assert msgs[1]["content"].startswith("MATERIAL:\nQuelle")

    def test_nummern_landen_an_der_zeile(self):
        roh = _antwort_mit_nummern([("text", [1, 2]), ("text", [3]), ("text", []),
                                    ("text", [4]), ("text", [5]), ("text", [6])])
        o = gliederung.parse_answer(roh, ROLLEN)
        assert o.rows[0].fact_ids == [1, 2] and o.rows[2].fact_ids == []

    def test_unbekannte_nummern_fallen_weg(self):
        roh = _antwort_mit_nummern([("text", [1, 99]), ("text", [3]), ("text", [2]),
                                    ("text", [4]), ("text", [5]), ("text", [6])])
        o = gliederung.parse_answer(roh, ROLLEN, gueltig={1, 2, 3, 4, 5, 6})
        assert o.rows[0].fact_ids == [1]

    def test_unsinn_statt_nummern_stuerzt_nicht(self):
        roh = json.dumps({"title": "D", "subtitle": "", "slides": [
            {"role": "text", "title": f"T{i}", "gist": "G", "fact_ids": "kaputt"}
            for i in range(6)]})
        assert gliederung.parse_answer(roh, ROLLEN).rows[0].fact_ids == []

    def test_die_regeln_nehmen_die_nummern_mit(self):
        """Rollen werden umgebogen und Ids vergeben, die Nummern muessen das ueberleben."""
        roh = _antwort_mit_nummern([("text_mit_bild", [1]), ("text_mit_bild", [2]), ("text", [3]),
                                    ("text", [4]), ("text", [5]), ("text", [6])])
        o = gliederung.parse_answer(roh, ROLLEN)
        assert [r.fact_ids for r in o.rows] == [[1], [2], [3], [4], [5], [6]]
        assert all(r.id for r in o.rows)
