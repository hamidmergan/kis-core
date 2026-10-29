"""The summary's operating numbers come from the admin panel, not the code."""

import pytest

from src.features.summary import settings as cfg
from src.limits import (
    SUMMARY_CALL_TIMEOUT_SECONDS,
    SUMMARY_MAX_OUTPUT_TOKENS,
    SUMMARY_READ_MAX_FACTS,
)


@pytest.fixture
def eingestellt(monkeypatch):
    """The admin panel as a dict, empty means nothing set."""
    werte: dict[str, str] = {}
    monkeypatch.setattr("src.database.get_setting",
                        lambda key, default="": werte.get(key, default))
    return werte


class TestRueckfall:
    """Without a usable entry the value from limits.py applies, never zero."""

    def test_ohne_eintrag_gilt_der_wert_aus_limits(self, eingestellt):
        assert cfg.facts_cap() == SUMMARY_READ_MAX_FACTS
        assert cfg.call_timeout() == SUMMARY_CALL_TIMEOUT_SECONDS
        assert cfg.output_tokens_cap() == SUMMARY_MAX_OUTPUT_TOKENS

    def test_ein_unlesbarer_eintrag_gilt_wie_kein_eintrag(self, eingestellt):
        eingestellt["summary_read_max_facts"] = "drei"
        assert cfg.facts_cap() == SUMMARY_READ_MAX_FACTS

    def test_eine_stumme_datenbank_kostet_den_lauf_nichts(self, monkeypatch):
        def fliegt(key, default=""):
            raise RuntimeError("keine Verbindung")

        monkeypatch.setattr("src.database.get_setting", fliegt)
        assert cfg.call_timeout() == SUMMARY_CALL_TIMEOUT_SECONDS


class TestSpanne:
    """A value outside the range is clamped to the nearest end, never passed through."""

    def test_zu_viele_fakten_werden_gekappt(self, eingestellt):
        eingestellt["summary_read_max_facts"] = "500"
        assert cfg.facts_cap() == 80

    def test_zu_wenige_fakten_werden_angehoben(self, eingestellt):
        eingestellt["summary_read_max_facts"] = "0"
        assert cfg.facts_cap() == 10

    def test_der_timeout_bleibt_unter_der_mauer_des_anbieters(self, eingestellt):
        # The provider drops a call at about 300 s, our limit must fire first.
        eingestellt["summary_call_timeout_seconds"] = "900"
        assert cfg.call_timeout() <= 300


class TestSofortWirksam:
    """The value is read on every call, a worker needs no restart."""

    def test_eine_aenderung_wirkt_ohne_neustart(self, eingestellt):
        eingestellt["summary_read_max_facts"] = "20"
        assert cfg.facts_cap() == 20
        eingestellt["summary_read_max_facts"] = "30"
        assert cfg.facts_cap() == 30

