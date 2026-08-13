"""Die Schreibweisen, die ein Kursplan sonst noch benutzt.

Eindeutiges liest das Suchmuster, Mehrdeutiges beurteilt das Modell mit dem Zusammenhang.
Die Trennlinie ist bewusst gezogen:

  03.Juli.2026  -> Muster. Eindeutig, und vorher fiel hier sogar das Jahr weg: es blieb
                   "03.Juli" uebrig und landete im laufenden Jahr.
  06.2026       -> Muster. Monat mit vierstelligem Jahr, wird ein Monatstermin.
  3.6.26        -> Modell. Sieht genauso aus wie eine Gliederungsnummer
                   ("3.6.26 Zusammenfassung"), das entscheidet nur der Zusammenhang.
  6.26          -> gar nicht. Kann Juni 2026 sein, ein Gliederungspunkt, eine Seitenzahl,
                   eine Kommazahl. Zu wenig Substanz fuer zu viel Fehlalarm.
"""

import pytest

from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _normalize_date,
    _normalize_month_date,
    _normalize_partial_date,
)
from src.features.ai_assistant.tasks.studio.schedule._regex import _date_candidates_in_text


def _funde(text):
    return [(roh, iso_teil, prec) for _s, _e, roh, iso_teil, prec in _date_candidates_in_text(text)]


# --- was das Suchmuster kann -------------------------------------------------

def test_punkt_vor_dem_jahr_behaelt_das_jahr():
    funde = _funde("Abgabe am 03.Juli.2026 um 18:00")
    assert funde == [("03.Juli.2026", True, "day")]
    assert _normalize_date("03.Juli.2026") == "2026-07-03"


def test_die_gewohnte_schreibweise_bleibt_unveraendert():
    assert _funde("Abgabe am 3. Juli 2026") == [("3. Juli 2026", True, "day")]
    assert _normalize_date("3. Juli 2026") == "2026-07-03"


def test_monat_mit_jahr_wird_ein_monatstermin():
    funde = _funde("Die Präsentationen finden im 06.2026 statt.")
    assert funde == [("06.2026", True, "month")]
    assert _normalize_month_date("06.2026") == "2026-06-01"


def test_ausgeschriebener_monat_mit_jahr():
    assert _normalize_month_date("Juli 2026") == "2026-07-01"
    assert _normalize_month_date("januar 2026") == "2026-01-01"


@pytest.mark.parametrize("wert", ["13.2026", "00.2026", "6.26", "0.2026"])
def test_unmoegliche_monate_und_zu_kurze_jahre_fallen_raus(wert):
    assert _normalize_month_date(wert) is None


def test_das_ganze_datum_schlaegt_den_monat_darin():
    """In "03.07.2026" steckt "07.2026". Gemeint ist das ganze Datum."""
    assert _funde("Abgabe am 03.07.2026") == [("03.07.2026", True, "day")]


def test_zweistellige_jahre_bleiben_dem_modell_ueberlassen():
    """Ein Muster wuerde hier auch jede Gliederungsnummer einsammeln."""
    assert _funde("Klausur am 3.6.26") == []
    assert _funde("Gliederung 3.6.26 Zusammenfassung") == []


def test_sechs_punkt_sechsundzwanzig_wird_bewusst_nicht_erkannt():
    """Die Form "6.26." sieht wie Tag.Monat aus, der Monat waere die 26. Den gibt es
    nicht, also faellt sie beim Umrechnen raus und erreicht den Zeitplan nie.
    Als Juni 2026 wird sie bewusst NICHT gelesen, dafuer ist sie zu mehrdeutig."""
    assert _funde("Die Abgabe erfolgt im 6.26.") == [("6.26.", False, "day")]
    assert _normalize_partial_date("6.26.") is None
    assert _normalize_month_date("6.26") is None


# --- die Genauigkeit reicht bis zum Kandidaten durch -------------------------

def test_jeder_fund_traegt_seine_genauigkeit():
    text = "Abgabe 03.07.2026, Vortraege im 06.2026, Rueckmeldung am 15. April"
    funde = _funde(text)
    assert ("03.07.2026", True, "day") in funde
    assert ("06.2026", True, "month") in funde
    assert ("15. April", False, "day") in funde
