"""Der Fortschritt zaehlt nur die Folien, die im Screencast landen."""

from src.tasks.screencast_tasks._pipeline import _fortschritt_vertonung


def test_ohne_ausschluss_bleibt_alles_wie_bisher():
    p = _fortschritt_vertonung([0, 1], 5, 2)
    assert p == {"step": "tts", "current": 2, "total": 5, "fertig": [0, 1], "nicht_dabei": []}


def test_ausgeschlossene_folien_stehen_getrennt():
    p = _fortschritt_vertonung([0, 2], 3, 2, {1, 4})
    assert p["nicht_dabei"] == [1, 4]
    assert p["fertig"] == [0, 2]


def test_die_liste_ist_immer_sortiert():
    assert _fortschritt_vertonung([2, 0], 3, 2, {4, 1})["fertig"] == [0, 2]
