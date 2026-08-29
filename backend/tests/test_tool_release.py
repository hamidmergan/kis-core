"""Die Freigabe eines Werkzeugs, getrennt von der Datenbank."""
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
