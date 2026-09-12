"""The model answer for a podcast: what counts as usable and what does not."""

import json

import pytest

from src.features.podcast.schemas import Line, Person, PodcastParams
from src.features.podcast.script import (
    ScriptUnusable,
    build_messages,
    clean_rephrased,
    parse_answer,
    rephrase_messages,
)


def _params(n=2, sprache="de", **kw):
    rollen = ["host", "expert", "student", "critic"]
    personen = [Person(name=f"P{i + 1}", role=rollen[i], voice_id=f"v{i}") for i in range(n)]
    return PodcastParams(language=sprache, persons=personen, **kw)


def _antwort(paare):
    return json.dumps({"lines": [{"speaker": s, "text": t} for s, t in paare]})


class TestAntwortLesen:
    def test_nimmt_die_beitraege_mit_sprecher(self):
        zeilen = parse_answer(_antwort([(0, "Hallo."), (1, "Guten Tag.")]), 2)
        assert [z.speaker for z in zeilen] == [0, 1]
        assert zeilen[0].text == "Hallo."

    def test_findet_das_json_auch_zwischen_geschwaetz(self):
        roh = "Gerne! Hier das Skript:\n```json\n" + _antwort([(0, "Eins."), (1, "Zwei.")]) + "\n```\nViel Erfolg!"
        assert len(parse_answer(roh, 2)) == 2

    def test_holt_einen_sprecher_ausserhalb_der_besetzung_zurueck(self):
        # Ein verirrter Index darf das Gespraech nicht auf eine Stimme zusammenfallen lassen.
        zeilen = parse_answer(_antwort([(0, "Eins."), (9, "Zwei.")]), 2)
        assert zeilen[1].speaker == 1
        assert parse_answer(_antwort([(0, "Eins."), (5, "Zwei."), (2, "Drei.")]), 3)[1].speaker == 2

    def test_wirft_bei_kaputtem_json(self):
        with pytest.raises(ScriptUnusable):
            parse_answer("das ist kein json", 2)

    def test_wirft_ohne_beitraege(self):
        with pytest.raises(ScriptUnusable):
            parse_answer(json.dumps({"lines": []}), 2)

    def test_wirft_bei_nur_einem_brauchbaren_beitrag(self):
        with pytest.raises(ScriptUnusable):
            parse_answer(_antwort([(0, "Allein."), (1, "   ")]), 2)

    def test_wirft_wenn_bei_zwei_personen_nur_eine_spricht(self):
        with pytest.raises(ScriptUnusable, match="eine Person"):
            parse_answer(_antwort([(0, "Eins."), (0, "Zwei.")]), 2)

    def test_laesst_eine_person_allein_sprechen(self):
        zeilen = parse_answer(_antwort([(0, "Eins."), (0, "Zwei.")]), 1)
        assert len(zeilen) == 2

    def test_kuerzt_einen_masslosen_beitrag(self):
        from src.limits import PODCAST_MAX_LINE_CHARS

        zeilen = parse_answer(_antwort([(0, "a" * 5000), (1, "Kurz.")]), 2)
        assert len(zeilen[0].text) == PODCAST_MAX_LINE_CHARS

    def test_deckelt_die_zahl_der_beitraege(self):
        from src.limits import PODCAST_MAX_LINES

        viele = [(i % 2, f"Satz {i}.") for i in range(PODCAST_MAX_LINES + 20)]
        assert len(parse_answer(_antwort(viele), 2)) == PODCAST_MAX_LINES


class TestPrompt:
    def test_nennt_die_besetzung_mit_nummer_und_rolle(self):
        text = build_messages("Material", _params(3))[1]["content"]
        assert "0: P1" in text and "1: P2" in text and "2: P3" in text

    def test_verbietet_den_wechsel_nicht_wenn_nur_einer_spricht(self):
        allein = build_messages("Material", _params(1))[1]["content"]
        assert "speaker ist immer 0" in allein
        zwei = build_messages("Material", _params(2))[1]["content"]
        assert "wechseln sich ab" in zwei

    def test_folgt_der_sprache_des_podcasts(self):
        assert "English" in build_messages("Material", _params(2, sprache="en"))[1]["content"]

    def test_nimmt_die_anweisung_mit(self):
        text = build_messages("M", _params(2, instructions="Bleib bei den Grundlagen"))[1]["content"]
        assert "Bleib bei den Grundlagen" in text

    def test_zielumfang_haengt_an_der_laenge(self):
        kurz = build_messages("M", _params(2, length="short"))[1]["content"]
        lang = build_messages("M", _params(2, length="long"))[1]["content"]
        assert "700" in kurz and "2800" in lang


class TestUmformulieren:
    def test_zeigt_dem_modell_das_umfeld(self):
        text = rephrase_messages(Line(id="b1", speaker=0, text="Der Satz."),
                                 _params(2), ["Davor.", "Danach."])[1]["content"]
        assert "Davor." in text and "Danach." in text and "Der Satz." in text

    def test_schaelt_die_namensnennung_ab(self):
        assert clean_rephrased("Lena: Der neue Satz.", "alt") == "Der neue Satz."

    def test_laesst_einen_doppelpunkt_im_satz_stehen(self):
        satz = "Es gilt der Merksatz: Spannung ist Widerstand mal Strom."
        assert clean_rephrased(satz, "alt") == satz

    def test_faellt_bei_leerer_antwort_auf_den_alten_text_zurueck(self):
        assert clean_rephrased("   ", "der alte Satz") == "der alte Satz"

    def test_schaelt_die_json_huelle_ab(self):
        assert clean_rephrased('{"text": "Der neue Satz." }', "alt") == "Der neue Satz."

    def test_nimmt_auch_einen_codeblock_um_das_json(self):
        roh = '```json\n{"text": "Der neue Satz."}\n```'
        assert clean_rephrased(roh, "alt") == "Der neue Satz."

    def test_verlangt_die_json_huelle_im_auftrag(self):
        nachricht = rephrase_messages(Line(id="b1", speaker=0, text="Der Satz."), _params(2), [])
        assert '{"text"' in nachricht[0]["content"]
