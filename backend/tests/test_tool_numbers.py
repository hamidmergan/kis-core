"""The shared pool of configurable numbers, every tool registers here."""

import pytest

from src.permissions_registry import ALL_PERMISSION_KEYS
from src.services import tool_numbers as tn


@pytest.fixture
def eingestellt(monkeypatch):
    """The admin panel as a dict, empty means nothing set."""
    werte: dict[str, str] = {}
    monkeypatch.setattr("src.database.get_setting",
                        lambda key, default="": werte.get(key, default))
    return werte


class TestDerVorrat:
    """Registered entries must be consistent, else it only shows up in production."""

    def test_kein_schluessel_kommt_zweimal_vor(self):
        schluessel = [n.key for n in tn.NUMBERS]
        assert len(schluessel) == len(set(schluessel))

    def test_jede_zahl_haengt_an_einem_bekannten_recht(self):
        for n in tn.NUMBERS:
            assert n.permission in ALL_PERMISSION_KEYS, n.key

    def test_jeder_standard_liegt_in_seiner_eigenen_spanne(self):
        for n in tn.NUMBERS:
            assert n.smallest <= n.default <= n.largest, n.key

    def test_die_spanne_ist_nie_verdreht(self):
        for n in tn.NUMBERS:
            assert n.smallest < n.largest, n.key

    def test_jede_zahl_nennt_ihr_werkzeug(self):
        for n in tn.NUMBERS:
            assert n.tool, n.key

    def test_ein_werkzeug_bekommt_seine_eigenen_zahlen(self):
        for n in tn.of_tool("summary"):
            assert n.tool == "summary"
        assert tn.of_tool("gibt_es_nicht") == ()


class TestLesen:
    """Without a usable entry the code default applies, never zero."""

    def test_ohne_eintrag_gilt_der_standard(self, eingestellt):
        for n in tn.NUMBERS:
            assert tn.value_of(n.key) == n.default

    def test_ein_unlesbarer_eintrag_gilt_wie_kein_eintrag(self, eingestellt):
        eingestellt["summary_read_max_facts"] = "drei"
        assert tn.value_of("summary_read_max_facts") == tn.BY_KEY["summary_read_max_facts"].default

    def test_eine_stumme_datenbank_kostet_den_lauf_nichts(self, monkeypatch):
        def fliegt(key, default=""):
            raise RuntimeError("keine Verbindung")

        monkeypatch.setattr("src.database.get_setting", fliegt)
        assert tn.value_of("summary_call_timeout_seconds") == 270

    def test_ein_wert_ueber_der_spanne_wird_ans_obere_ende_gezogen(self, eingestellt):
        eingestellt["summary_read_max_facts"] = "500"
        assert tn.value_of("summary_read_max_facts") == 80

    def test_ein_wert_unter_der_spanne_wird_ans_untere_ende_gezogen(self, eingestellt):
        eingestellt["summary_read_max_facts"] = "0"
        assert tn.value_of("summary_read_max_facts") == 10

    def test_eine_aenderung_wirkt_ohne_neustart(self, eingestellt):
        eingestellt["summary_read_max_facts"] = "20"
        assert tn.value_of("summary_read_max_facts") == 20
        eingestellt["summary_read_max_facts"] = "30"
        assert tn.value_of("summary_read_max_facts") == 30

    def test_eine_unbekannte_zahl_ist_ein_fehler_kein_stiller_null(self):
        with pytest.raises(KeyError):
            tn.value_of("gibt_es_nicht")


class TestRecht:
    def test_das_recht_einer_zahl_ist_abfragbar(self):
        assert tn.permission_for("summary_read_max_facts") == "settings.werkzeuge.limits"

    def test_eine_unbekannte_zahl_haengt_an_keinem_recht(self):
        assert tn.permission_for("gibt_es_nicht") is None
