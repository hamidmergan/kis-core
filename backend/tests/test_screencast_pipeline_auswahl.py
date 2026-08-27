"""The counter reports the slides to be spoken, not the slides in the video."""

from src.tasks.screencast_tasks._pipeline import _fortschritt_vertonung


def test_der_nenner_ist_die_zahl_der_zu_sprechenden_folien():
    p = _fortschritt_vertonung({0, 1}, 2, 2)
    assert p == {"step": "tts", "current": 2, "total": 2, "fertig": [0, 1], "nicht_dabei": []}


def test_schon_vorhandene_folien_stehen_von_anfang_an_in_fertig():
    p = _fortschritt_vertonung({0, 1, 2, 3, 4}, 2, 0)
    assert p["fertig"] == [0, 1, 2, 3, 4]
    assert p["current"] == 0


def test_ausgeschlossene_folien_stehen_in_nicht_dabei_und_nicht_in_fertig():
    p = _fortschritt_vertonung({0, 2}, 3, 2, {1, 4})
    assert p["nicht_dabei"] == [1, 4]
    assert p["fertig"] == [0, 2]
    assert 1 not in p["fertig"]
    assert 4 not in p["fertig"]


def test_die_liste_ist_immer_sortiert():
    assert _fortschritt_vertonung({2, 0}, 3, 2, {4, 1})["fertig"] == [0, 2]
