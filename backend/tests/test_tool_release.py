"""Releasing a tool, separate from the database."""
from src.services.tool_release import is_released


def test_normales_werkzeug_ist_frei():
    assert is_released("tts", disabled=set(), overrides=set()) is True


def test_abgeschaltetes_werkzeug_ist_gesperrt():
    assert is_released("tts", disabled={"tts"}, overrides=set()) is False


def test_abschalten_schlaegt_die_ausnahme():
    assert is_released("tts", disabled={"tts"}, overrides={"tts"}) is False


def test_standardmaessig_aus_bleibt_aus_ohne_ausnahme(monkeypatch):
    from src.services import tool_release
    monkeypatch.setattr(tool_release, "DEFAULT_DISABLED_TOOLS", {"image"})
    assert tool_release.is_released("image", disabled=set(), overrides=set()) is False


def test_standardmaessig_aus_wird_durch_ausnahme_frei(monkeypatch):
    from src.services import tool_release
    monkeypatch.setattr(tool_release, "DEFAULT_DISABLED_TOOLS", {"image"})
    assert tool_release.is_released("image", disabled=set(), overrides={"image"}) is True


def test_standardliste_wird_aus_der_registry_nachgeladen(monkeypatch):
    """Without monkeypatch the real list must come from the admin management."""
    from src.services import tool_release
    from src.routes.admin._registries import DEFAULT_DISABLED_TOOLS as registry_default
    monkeypatch.setattr(tool_release, "DEFAULT_DISABLED_TOOLS", None)
    tool_release.is_released("tts", disabled=set(), overrides=set())
    assert tool_release.DEFAULT_DISABLED_TOOLS is registry_default
