"""The job folder of a podcast: ids, fingerprints and what may keep its audio."""

import pytest

from src.features.podcast import store
from src.features.podcast.schemas import Line


def _line(n, text="Ein Satz."):
    return Line(id=f"b{n}", speaker=0, text=text)


class TestIds:
    def test_vergibt_dem_neuen_beitrag_die_naechste_freie_nummer(self):
        zeilen = store.next_ids([_line(0), Line(id="", speaker=1, text="Neu."), _line(2)])
        assert [z.id for z in zeilen] == ["b0", "b1", "b2"]

    def test_laesst_bestehende_ids_stehen(self):
        zeilen = store.next_ids([_line(5), _line(9)])
        assert [z.id for z in zeilen] == ["b5", "b9"]

    def test_ersetzt_eine_erfundene_id_aus_dem_browser(self):
        zeilen = store.next_ids([_line(0), Line(id="neu1", speaker=0, text="Frisch.")])
        assert zeilen[1].id == "b1"

    def test_loest_eine_doppelte_id_auf(self):
        zeilen = store.next_ids([_line(0), _line(0)])
        assert len({z.id for z in zeilen}) == 2


class TestFingerabdruck:
    def test_gleicher_text_und_gleiche_stimme_behalten_den_ton(self):
        line = _line(0)
        vertont = {"b0": store.fingerprint(line, "anna", 1.0)}
        assert store.needs_voice(line, vertont, "anna", 1.0) is False

    def test_geaenderter_text_braucht_neuen_ton(self):
        vertont = {"b0": store.fingerprint(_line(0, "Alt."), "anna", 1.0)}
        assert store.needs_voice(_line(0, "Neu."), vertont, "anna", 1.0) is True

    def test_andere_stimme_braucht_neuen_ton(self):
        line = _line(0)
        vertont = {"b0": store.fingerprint(line, "anna", 1.0)}
        assert store.needs_voice(line, vertont, "ben", 1.0) is True

    def test_anderes_tempo_braucht_neuen_ton(self):
        line = _line(0)
        vertont = {"b0": store.fingerprint(line, "anna", 0.9)}
        assert store.needs_voice(line, vertont, "anna", 1.2) is True

    def test_reine_randleerzeichen_aendern_nichts(self):
        vertont = {"b0": store.fingerprint(_line(0, "Ein Satz."), "anna", 1.0)}
        assert store.needs_voice(_line(0, "  Ein Satz.  "), vertont, "anna", 1.0) is False

    def test_ein_unbekannter_beitrag_braucht_ton(self):
        assert store.needs_voice(_line(3), {}, "anna", 1.0) is True


class TestDateinamen:
    def test_haengt_den_ton_an_die_id_nicht_an_die_position(self):
        assert store.audio_name("b7") == "audio/b7.mp3"
