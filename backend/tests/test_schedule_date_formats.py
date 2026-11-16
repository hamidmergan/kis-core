"""The pattern reads unambiguous date forms, the model judges ambiguous ones."""

from src.features.ai_assistant.tasks.studio.schedule._regex import _date_candidates_in_text


def _funde(text):
    return [(roh, iso_teil, prec) for _s, _e, roh, iso_teil, prec in _date_candidates_in_text(text)]


# --- what the search pattern can do ------------------------------------------

def test_punkt_vor_dem_jahr_behaelt_das_jahr():
    funde = _funde("Abgabe am 03.Juli.2026 um 18:00")
    assert funde == [("03.Juli.2026", True, "day")]


def test_die_gewohnte_schreibweise_bleibt_unveraendert():
    assert _funde("Abgabe am 3. Juli 2026") == [("3. Juli 2026", True, "day")]


def test_monat_mit_jahr_wird_ein_monatstermin():
    funde = _funde("Die Präsentationen finden im 06.2026 statt.")
    assert funde == [("06.2026", True, "month")]


def test_das_ganze_datum_schlaegt_den_monat_darin():
    """'03.07.2026' contains '07.2026', the whole date is meant."""
    assert _funde("Abgabe am 03.07.2026") == [("03.07.2026", True, "day")]


def test_zweistellige_jahre_werden_gefunden_das_modell_sortiert_gliederungen_aus():
    """The pattern also collects section numbers, the model sees the block and decides."""
    assert _funde("Klausur am 3.6.26") == [("3.6.26", True, "day")]
    assert _funde("Gliederung 3.6.26 Zusammenfassung") == [("3.6.26", True, "day")]


def test_sechs_punkt_sechsundzwanzig_geht_als_fund_ans_modell():
    """The pattern only flags the ambiguous form, the model reads it."""
    assert _funde("Die Abgabe erfolgt im 6.26.") == [("6.26.", False, "day")]


# --- the precision reaches the candidate --------------------------------------

def test_jeder_fund_traegt_seine_genauigkeit():
    text = "Abgabe 03.07.2026, Vortraege im 06.2026, Rueckmeldung am 15. April"
    funde = _funde(text)
    assert ("03.07.2026", True, "day") in funde
    assert ("06.2026", True, "month") in funde
    assert ("15. April", False, "day") in funde
