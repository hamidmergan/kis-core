"""One admin field, the same number for every overview tool."""

import pytest

from src.features.ai_assistant.tasks import _context_budget as cb


@pytest.fixture
def feld(monkeypatch):
    """The admin field under test control."""
    state = {"wert": 500000}
    monkeypatch.setattr("src.database.get_setting",
                        lambda key, default: str(state["wert"]))
    monkeypatch.setattr("src.services.model_limits.profile_for_feature", lambda feature="chat": None)
    return state


def test_every_overview_tool_reads_the_whole_field(feld):
    assert cb.tool_context_budget() == 500000
    feld["wert"] = 100000
    assert cb.tool_context_budget() == 100000


def test_the_field_is_the_one_of_the_overview_tools(monkeypatch):
    seen = {}

    def get_setting(key, default):
        seen["key"] = key
        return default

    monkeypatch.setattr("src.database.get_setting", get_setting)
    monkeypatch.setattr("src.services.model_limits.profile_for_feature", lambda feature="chat": None)
    assert cb.tool_context_budget() == 500000
    assert seen["key"] == "aia_tool_context_max_chars"


def test_a_typo_in_the_admin_area_is_capped(feld):
    feld["wert"] = 5000000
    assert cb.tool_context_budget() == 1000000


def test_the_same_material_fills_the_same_amount_for_every_tool(feld):
    # No shares any more: two tools, one field, one result.
    quellen = [(1, "q1.pdf", [{"page_number": p, "content": "x" * 1000}
                              for p in range(1, 900)])]
    erster = cb.fill_sources_evenly(quellen)
    zweiter = cb.fill_sources_evenly(quellen)
    assert len(erster[0][2]) == len(zweiter[0][2])


def _fenster(monkeypatch, fenster, quelle):
    from src.services import model_limits as ml
    profil = None if fenster is None else ml.ModelProfile(fenster, quelle, False, "")
    monkeypatch.setattr(ml, "profile_for_feature", lambda feature="chat": profil)


@pytest.mark.parametrize("quelle", ["gesetzt", "gemessen"])
def test_ein_kleines_bekanntes_fenster_ist_ein_kleines_modell(monkeypatch, quelle):
    monkeypatch.setattr("src.database.get_setting", lambda key, default: default)
    # 16k tokens cannot hold the overview budget, 32k already can.
    _fenster(monkeypatch, 16384, quelle)
    assert cb.small_model() is True


@pytest.mark.parametrize("fenster,quelle", [
    (262144, "gesetzt"),   # myLab: entered by hand, but bigger than the field needs
    (262144, "gemessen"),  # GWDG measures 262k, bigger than the field needs
    (32768, "gelernt"),    # learned windows never decide, they may stem from a rate limit
    (None, "gesetzt"),     # nothing known about the model
])
def test_cloud_anbieter_bleiben_beim_gewohnten_weg(monkeypatch, fenster, quelle):
    monkeypatch.setattr("src.database.get_setting", lambda key, default: default)
    _fenster(monkeypatch, fenster, quelle)
    assert cb.small_model() is False
