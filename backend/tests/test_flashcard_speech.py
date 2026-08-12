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


def test_null_als_anbieternummer_ist_ungueltig(settings):
    """Null existiert nicht als Provider-ID (SERIAL beginnt bei 1)."""
    settings["aia_flashcard_voice_provider_id"] = "0"
    settings["aia_flashcard_voice_id"] = "alloy"
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False


def test_negative_anbieternummer_ist_ungueltig(settings):
    """Negative Nummern existieren nicht als Provider-IDs."""
    settings["aia_flashcard_voice_provider_id"] = "-5"
    settings["aia_flashcard_voice_id"] = "alloy"
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False


# --- das Sprechen selbst -----------------------------------------------------

from fastapi import HTTPException


class _Client:
    """Ein Anbieter, der die ersten ``fehler`` Versuche wirft und dann liefert."""

    def __init__(self, fehler=0):
        self.fehler = fehler
        self.aufrufe = []

    def synthesize_chunk(self, text, *, voice_id, speed=1.0, **kwargs):
        self.aufrufe.append((text, voice_id))
        if len(self.aufrufe) <= self.fehler:
            raise RuntimeError("TTS API error (500): Internal Server Error")
        return b"ID3-audio"


def _mit_client(monkeypatch, client):
    monkeypatch.setattr(
        "src.dependencies.get_tts_client_for_provider", lambda pid: client
    )


def test_ohne_eingerichtete_stimme_gibt_es_503(settings):
    with pytest.raises(HTTPException) as fehler:
        speech.synthesize_sentence("Ich treffe mich morgen.")
    assert fehler.value.status_code == 503


def test_der_satz_geht_mit_der_eingestellten_stimme_raus(settings, monkeypatch):
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"
    client = _Client()
    _mit_client(monkeypatch, client)

    assert speech.synthesize_sentence("Ich treffe mich morgen.") == b"ID3-audio"
    assert client.aufrufe == [("Ich treffe mich morgen.", "alloy")]


def test_ein_fehlschlag_wird_wiederholt(settings, monkeypatch):
    """Gemessen am 2026-08-12: myLab hat eine Anfrage mit 500 abgewiesen und beim
    zweiten Versuch geliefert. Dafür soll niemand einen Fehler sehen."""
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"
    client = _Client(fehler=1)
    _mit_client(monkeypatch, client)

    assert speech.synthesize_sentence("Ein Satz.") == b"ID3-audio"
    assert len(client.aufrufe) == 2


def test_zwei_fehlschlaege_ergeben_503(settings, monkeypatch):
    """Zweimal daneben heißt: der Anbieter ist gerade nicht zu gebrauchen. Kein
    dritter Versuch, der Lernende wartet sonst fünfzehn Sekunden auf nichts."""
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"
    client = _Client(fehler=2)
    _mit_client(monkeypatch, client)

    with pytest.raises(HTTPException) as fehler:
        speech.synthesize_sentence("Ein Satz.")
    assert fehler.value.status_code == 503
    assert len(client.aufrufe) == 2


def test_kein_anbieter_hinter_der_nummer_gibt_503(settings, monkeypatch):
    """Die Nummer zeigt auf einen gelöschten oder abgeschalteten Anbieter."""
    settings["aia_flashcard_voice_provider_id"] = "999"
    settings["aia_flashcard_voice_id"] = "alloy"
    monkeypatch.setattr(
        "src.dependencies.get_tts_client_for_provider", lambda pid: None
    )
    with pytest.raises(HTTPException) as fehler:
        speech.synthesize_sentence("Ein Satz.")
    assert fehler.value.status_code == 503


def test_abholt_fehler_gibt_503_kein_absturz(settings, monkeypatch):
    """Wenn get_tts_client_for_provider selbst wirft (z.B. fehlende Modell-Konfiguration),
    wird daraus ein 503, kein Absturz."""
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"

    def _wirft_runtime_error(pid):
        raise RuntimeError("Modell nicht konfiguriert")

    monkeypatch.setattr("src.dependencies.get_tts_client_for_provider", _wirft_runtime_error)
    with pytest.raises(HTTPException) as fehler:
        speech.synthesize_sentence("Ein Satz.")
    assert fehler.value.status_code == 503
