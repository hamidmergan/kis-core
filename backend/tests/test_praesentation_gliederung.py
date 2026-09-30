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
        assert msgs[1]["content"].startswith("/no_think\nMATERIAL:\nQuelle")

    def test_erklaert_die_nummern_je_nach_grundlage(self):
        stellen = gliederung.build_messages("Q", PraesentationParams(), ROLLEN, "stellen")
        themen = gliederung.build_messages("Q", PraesentationParams(), ROLLEN, "themen")
        assert "numbered passages" in stellen[0]["content"]
        assert "numbered list of topics" in themen[0]["content"]

    def test_die_refs_einer_folie_werden_zu_stellen(self):
        raw = json.dumps({"title": "D", "slides": [
            {"role": "text", "title": f"F{i}", "gist": "g", "refs": [i, "7-8"]} for i in range(1, 5)]})
        o = gliederung.parse_answer(raw, ROLLEN, lambda refs: [int(str(r).split("-")[0]) for r in refs])
        assert o.rows[1].stellen == [2, 7]

    def test_anweisung_kommt_nach_dem_material(self):
        msgs = gliederung.build_messages("Q", PraesentationParams(instructions="nur Kapitel 2"), ROLLEN)
        text = msgs[1]["content"]
        assert text.rindex('"nur Kapitel 2"') > text.rindex("MATERIAL")
        assert "never add content the material does not hold" in text


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








class TestAbdeckung:
    def test_mehrere_dateien_muessen_alle_vorkommen(self):
        system = gliederung.build_messages("Q", PraesentationParams(), ROLLEN,
                                           dateien=["a.pdf", "b.pdf"], ziel=26)[0]["content"]
        assert "2 files: a.pdf, b.pdf" in system and "EVERY one" in system
        assert "Plan around 26 slides" in system

    def test_eine_fehlende_datei_wird_beim_zweiten_versuch_genannt(self):
        user = gliederung.build_messages("Q", PraesentationParams(), ROLLEN,
                                         fehlt=["b.pdf"])[1]["content"]
        assert user.rstrip().endswith("how much of the material it holds: b.pdf")


class TestWieNotebookLM:
    def test_eine_grosse_datei_bekommt_hoechstens_doppelt_so_viele_folien(self):
        system = gliederung.build_messages("Q", PraesentationParams(), ROLLEN,
                                           dateien=["a.pdf", "b.pdf"])[0]["content"]
        assert "never more than twice the slides of the smallest" in system

    def test_der_schluss_ist_ein_gedanke_kein_dank(self):
        system = gliederung.build_messages("Q", PraesentationParams(), ROLLEN)[0]["content"]
        assert "never a thank-you" in system

    def test_vor_dem_schluss_eine_uebersicht_ueber_alle_dokumente(self):
        system = gliederung.build_messages("Q", PraesentationParams(), ROLLEN,
                                           dateien=["a.pdf", "b.pdf"])[0]["content"]
        assert "overview that compares the documents" in system
        assert "deadlines, who is responsible and the consequences" in system
        assert "role text and a gist that asks for a table" in system

    def test_bildfolien_hoechstens_jede_fuenfte(self):
        rollen = ["d"] + ["text_mit_bild", "text"] * 7 + ["a"]
        o = gliederung.parse_answer(_antwort(rollen), ROLLEN)
        mit_bild = [r for r in o.rows if r.role in ("text_mit_bild", "bild_gross")]
        assert len(mit_bild) == len(o.rows) // 5

    def test_das_folienziel_wie_notebooklm(self):
        assert gliederung.ziel_folien(500_000) == 16
        assert gliederung.ziel_folien(20_000) == 8


def _karte(**stellen_je_datei):
    from src.services import text_map as tm
    from src.services.source_reading import Piece, Source
    return tm.Karte([Source(dateiname=n, fassung="x", text="T" * k, seiten=1,
                            stuecke=[Piece(seite=1, von=i, bis=i + 1) for i in range(k)])
                     for n, k in stellen_je_datei.items()])


class TestFolienJeDatei:
    def test_die_vier_gesetze_wie_notebooklm(self):
        karte = _karte(hwo=337, entgfg=29, bdsg=215, agg=61)
        assert gliederung.folien_je_datei(karte, 13) == {"hwo": 4, "entgfg": 2, "bdsg": 4, "agg": 3}

    def test_nie_mehr_als_doppelt_so_viele_wie_die_kleinste(self):
        anteile = gliederung.folien_je_datei(_karte(gross=1000, klein=1), 12)
        assert sum(anteile.values()) == 12 and max(anteile.values()) <= 2 * min(anteile.values())

    def test_eine_datei_oder_zu_wenige_folien_ohne_vorgabe(self):
        assert gliederung.folien_je_datei(_karte(a=10), 10) == {}
        assert gliederung.folien_je_datei(_karte(a=1, b=1, c=1), 2) == {}

    def test_der_prompt_nennt_die_zahlen(self):
        system = gliederung.build_messages("Q", PraesentationParams(), ROLLEN, dateien=["a", "b"],
                                           anteile={"a": 4, "b": 2})[0]["content"]
        assert "a: 4, b: 2" in system and "counts for the file it draws on most" in system


class TestSchief:
    def _zeilen(self, *refs):
        return [OutlineRow(role="text", title="T", stellen=list(r)) for r in refs]

    def test_nennt_nur_die_dateien_neben_ihrem_anteil(self):
        karte = _karte(hwo=337, entgfg=29, bdsg=215, agg=61)
        hwo, entgfg, bdsg, agg = [1], [338], [367], [582]
        rows = self._zeilen(*[hwo] * 6, *[entgfg] * 2, *[bdsg] * 3, *[agg] * 2)
        assert gliederung.schief(rows, karte) == ["hwo: 6 slides instead of 4"]

    def test_eine_folie_daneben_ist_ausgewogen(self):
        karte = _karte(hwo=337, entgfg=29, bdsg=215, agg=61)
        rows = self._zeilen(*[[1]] * 5, *[[338]] * 2, *[[367]] * 3, *[[582]] * 3)
        assert gliederung.schief(rows, karte) == []

    def test_eine_ausgelassene_datei_ist_schief(self):
        karte = _karte(hwo=337, entgfg=29, bdsg=215, agg=61)
        rows = self._zeilen(*[[1]] * 8, *[[367]] * 3, *[[582]] * 2)
        assert "entgfg: 0 slides instead of 2" in gliederung.schief(rows, karte)
