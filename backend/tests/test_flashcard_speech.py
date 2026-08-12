"""Welche Stimme den Beispielsatz einer Lernkarte spricht.

Zwei Einstellungen, Anbieter und Stimme, beide leer ausgeliefert. Solange eine
fehlt, gibt es den Lautsprecher nicht. Absicht: eine fest eingebaute
Anbieternummer wäre bei der nächsten Hochschule falsch, dort legt die Verwaltung
ihre Anbieter selbst an und bekommt andere Nummern.
"""

import pytest

from src.services import aia_flashcard_speech as speech


@pytest.fixture
def settings(monkeypatch):
    """Die Einstellungstabelle als Wörterbuch, ohne Datenbank."""
    werte: dict[str, str] = {}

    def get_setting(key, default=""):
        return werte.get(key, default)

    monkeypatch.setattr("src.database.get_setting", get_setting)
    return werte


def test_ohne_einstellungen_ist_nichts_gewaehlt(settings):
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False


def test_nur_anbieter_reicht_nicht(settings):
    """Ein Anbieter ohne Stimme kann nicht sprechen, der Knopf bliebe wirkungslos."""
    settings["aia_flashcard_voice_provider_id"] = "21"
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False


def test_nur_stimme_reicht_nicht(settings):
    settings["aia_flashcard_voice_id"] = "alloy"
    assert speech.configured_voice() is None


def test_beides_gesetzt_ergibt_das_paar(settings):
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"
    assert speech.configured_voice() == (21, "alloy")
    assert speech.speech_enabled() is True


def test_leerzeichen_zaehlen_als_nicht_gesetzt(settings):
    settings["aia_flashcard_voice_provider_id"] = "  "
    settings["aia_flashcard_voice_id"] = "  "
    assert speech.configured_voice() is None


def test_unsinn_als_anbieternummer_schaltet_ab(settings):
    """Eine kaputte Einstellung darf keinen Absturz erzeugen, nur einen fehlenden Knopf."""
    settings["aia_flashcard_voice_provider_id"] = "kokoro"
    settings["aia_flashcard_voice_id"] = "alloy"
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False
