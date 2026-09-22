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
        assert msgs[1]["content"].startswith("FACTS, one per line, numbered:\nQuelle")

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




class TestFaktennummern:
    """Die Gliederung zeigt auf den Vorrat, damit jede Folie nur ihre Fakten sieht."""






