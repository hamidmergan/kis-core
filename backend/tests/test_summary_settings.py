"""Die Betriebszahlen der Zusammenfassung kommen aus dem Adminbereich, nicht aus dem Code."""

import pytest

from src.features.summary import settings as cfg
from src.limits import (
    SUMMARY_CALL_TIMEOUT_SECONDS,
    SUMMARY_MAP_CONCURRENCY,
    SUMMARY_MAX_CHARS_PER_SOURCE,
    SUMMARY_MAX_OUTPUT_TOKENS,
    SUMMARY_MAX_SOURCES,
    SUMMARY_READ_MAX_FACTS,
)


@pytest.fixture
def eingestellt(monkeypatch):
    """Der Adminbereich als Wörterbuch, leer heißt nichts eingestellt."""
    werte: dict[str, str] = {}
    monkeypatch.setattr("src.database.get_setting",
                        lambda key, default="": werte.get(key, default))
    return werte


class TestRueckfall:
    """Ohne brauchbaren Eintrag gilt der Wert aus limits.py, nie eine Null."""

    def test_ohne_eintrag_gilt_der_wert_aus_limits(self, eingestellt):
        assert cfg.map_concurrency() == SUMMARY_MAP_CONCURRENCY
        assert cfg.chars_per_source() == SUMMARY_MAX_CHARS_PER_SOURCE
        assert cfg.facts_cap() == SUMMARY_READ_MAX_FACTS
        assert cfg.call_timeout() == SUMMARY_CALL_TIMEOUT_SECONDS
        assert cfg.output_tokens_cap() == SUMMARY_MAX_OUTPUT_TOKENS

    def test_ein_unlesbarer_eintrag_gilt_wie_kein_eintrag(self, eingestellt):
        eingestellt["summary_map_concurrency"] = "drei"
        assert cfg.map_concurrency() == SUMMARY_MAP_CONCURRENCY

    def test_eine_stumme_datenbank_kostet_den_lauf_nichts(self, monkeypatch):
        def fliegt(key, default=""):
            raise RuntimeError("keine Verbindung")

        monkeypatch.setattr("src.database.get_setting", fliegt)
        assert cfg.call_timeout() == SUMMARY_CALL_TIMEOUT_SECONDS


class TestSpanne:
    """Ein Wert außerhalb der Spanne wird ans nächste Ende gezogen, nie durchgereicht."""

    def test_zu_hohe_nebenlaeufigkeit_wird_gekappt(self, eingestellt):
        eingestellt["summary_map_concurrency"] = "50"
        assert cfg.map_concurrency() == 5

    def test_null_gleichzeitige_aufrufe_gibt_es_nicht(self, eingestellt):
        eingestellt["summary_map_concurrency"] = "0"
        assert cfg.map_concurrency() == 1

    def test_der_timeout_bleibt_unter_der_mauer_des_anbieters(self, eingestellt):
        # Der Anbieter wirft einen Aufruf bei etwa 300 s weg, unsere Grenze muss vorher greifen.
        eingestellt["summary_call_timeout_seconds"] = "900"
        assert cfg.call_timeout() <= 300


class TestSofortWirksam:
    """Der Wert wird bei jedem Aufruf gelesen, ein Arbeiter braucht keinen Neustart."""

    def test_eine_aenderung_wirkt_ohne_neustart(self, eingestellt):
        eingestellt["summary_map_concurrency"] = "1"
        assert cfg.map_concurrency() == 1
        eingestellt["summary_map_concurrency"] = "4"
        assert cfg.map_concurrency() == 4


class TestGesamtmenge:
    """Die Gesamtgrenze folgt der Dateigrenze, sonst weist sie ab, was je Datei erlaubt ist."""

    def test_die_gesamtgrenze_folgt_der_eingestellten_dateigrenze(self, eingestellt):
        eingestellt["summary_max_chars_per_source"] = "100000"
        assert cfg.total_chars() == SUMMARY_MAX_SOURCES * 100_000
