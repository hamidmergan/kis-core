"""Gleichzeitig vertonte Folien: Einstellung statt Konstante.

Warum das eine Einstellung sein muss: die Vertonung ist reine Wartezeit am
Anbieter und macht bei einem Screencast über 95 Prozent der Laufzeit aus. Wie
viele Anfragen ein Anbieter verträgt, hängt an seiner Hardware, nicht an
unserem Code. Ein geteilter Dienst verträgt wenig, eine eigene GPU ein
Vielfaches. Ohne Einstellung müsste dafür jedes Mal neu gebaut werden.

Nach oben gedeckelt, weil eine Fehleingabe im Admin sonst den Sprachdienst der
ganzen Hochschule mit hunderten gleichzeitigen Anfragen fluten würde.
"""

import pytest

from src.limits import SCREENCAST_TTS_DEFAULT_PARALLELISM, SCREENCAST_TTS_MAX_PARALLELISM
from src.services.screencast import generation


@pytest.fixture
def with_setting(monkeypatch):
    """Legt einen Wert in die Einstellung, ohne Datenbank."""
    from src import database as db

    def _apply(value):
        asked: list[str] = []

        def _get_setting(key, default=None):
            asked.append(key)
            return default if value is None else value

        monkeypatch.setattr(db, "get_setting", _get_setting)
        return asked
    return _apply


def test_default_when_nothing_is_stored(with_setting):
    with_setting(None)
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_DEFAULT_PARALLELISM


def test_admin_value_wins(with_setting):
    with_setting("8")
    assert generation.resolve_tts_parallelism() == 8


def test_value_above_ceiling_is_capped(with_setting):
    """Eine 500 im Feld darf nicht 500 gleichzeitige Anfragen bedeuten."""
    with_setting("500")
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_MAX_PARALLELISM


@pytest.mark.parametrize("stored", ["0", "-3"])
def test_nonsense_falls_back_to_default(with_setting, stored):
    """0 würde jede Vertonung blockieren, negativ ist unmöglich."""
    with_setting(stored)
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_DEFAULT_PARALLELISM


def test_unreadable_value_falls_back_to_default(with_setting):
    with_setting("acht")
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_DEFAULT_PARALLELISM


def test_database_failure_does_not_break_rendering(monkeypatch):
    """Ohne Datenbank soll der Screencast trotzdem rendern, nur eben mit Standard."""
    from src import database as db

    def _broken(*a, **kw):
        raise RuntimeError("keine Verbindung")

    monkeypatch.setattr(db, "get_setting", _broken)
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_DEFAULT_PARALLELISM


def test_default_is_greater_than_one():
    """Der alte Wert 1 machte eine 90-Minuten-Vorlesung unmöglich: 82 Minuten
    Vertonung gegen ein Zeitlimit, das darunter lag."""
    assert SCREENCAST_TTS_DEFAULT_PARALLELISM > 1
