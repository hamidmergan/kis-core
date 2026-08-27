"""Cached finished slides have to go into the preview at once, without waiting for the voicing."""

from src.services.screencast.auswahl import zu_sprechende_folien


def test_folien_aus_dem_vorrat_zaehlen_nicht_zum_sprechen():
    clip_folien = list(range(27))
    schon_da = set(range(25))
    scripts = ["Text."] * 27
    assert zu_sprechende_folien(clip_folien, scripts, schon_da) == 2
    assert set(schon_da) == schon_da
    assert len(set(schon_da)) == 25


def test_leeres_skript_zaehlt_nicht_zum_sprechen():
    clip_folien = [0, 1, 2]
    scripts = ["Text.", "   ", "Text."]
    assert zu_sprechende_folien(clip_folien, scripts, set()) == 2


def test_ohne_vorrat_ist_es_die_zahl_der_folien_mit_skript():
    clip_folien = [0, 1, 2, 3]
    scripts = ["Eins.", "Zwei.", "Drei.", "Vier."]
    assert zu_sprechende_folien(clip_folien, scripts, set()) == 4
