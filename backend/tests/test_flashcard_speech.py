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


# --- der Vorrat --------------------------------------------------------------
#
# Ein Satz kostet vier bis fuenf Sekunden beim Anbieter. Ohne Vorrat zahlt jede Person
# im Kurs diesen Preis erneut, und dieselbe Person nach jedem Neuladen noch einmal.
# Geprueft wird deshalb vor allem eines: dass der Schluessel am SATZ haengt und nicht
# an der Karte, und dass ein kaputter Vorrat das Vorlesen nicht verhindert.

from src.features.ai_assistant.repository import speech_cache


class _Vorrat:
    """Der Vorrat als Woerterbuch, ohne Datenbank."""

    def __init__(self, kaputt_beim_lesen=False, kaputt_beim_schreiben=False):
        self.inhalt = {}
        self.kaputt_beim_lesen = kaputt_beim_lesen
        self.kaputt_beim_schreiben = kaputt_beim_schreiben
        self.gelesen = []

    def get(self, key):
        self.gelesen.append(key)
        if self.kaputt_beim_lesen:
            raise RuntimeError("Datenbank weg")
        return self.inhalt.get(key)

    def put(self, key, audio):
        if self.kaputt_beim_schreiben:
            raise RuntimeError("Datenbank weg")
        self.inhalt[key] = audio


@pytest.fixture(autouse=True)
def vorrat(monkeypatch):
    """Der Vorrat als Woerterbuch, fuer JEDEN Test dieser Datei.

    Autouse mit Absicht: ohne ihn griffe ``synthesize_sentence`` auf die echte
    Datenbank zu. Ein Test schriebe dann seinen Platzhalter-Ton dorthin, und der
    naechste Lauf bekaeme ihn aus dem Vorrat zurueck, ohne den Anbieter je zu
    fragen. Genau das ist hier einmal passiert: zwei Tests aus der Zeit vor dem
    Vorrat schlugen beim zweiten Lauf fehl, weil sie sich selbst vergiftet hatten.
    """
    return _mit_vorrat(monkeypatch, _Vorrat())


def _mit_vorrat(monkeypatch, vorrat):
    monkeypatch.setattr(speech_cache, "get", vorrat.get)
    monkeypatch.setattr(speech_cache, "put", vorrat.put)
    return vorrat


def _eingerichtet(settings):
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"


# --- der Fingerabdruck -------------------------------------------------------

def test_derselbe_satz_ergibt_denselben_schluessel():
    a = speech_cache.fingerprint("Ich treffe mich morgen.", 21, "alloy", 1.0)
    b = speech_cache.fingerprint("Ich treffe mich morgen.", 21, "alloy", 1.0)
    assert a == b


def test_zeilenumbrueche_und_randleerzeichen_aendern_den_schluessel_nicht():
    """Der Sprachclient faltet sie ohnehin zusammen. Taeten wir es hier nicht, bekaemen
    zwei identisch gesprochene Saetze verschiedene Schluessel und der Vorrat griffe nie."""
    a = speech_cache.fingerprint("Ich treffe mich morgen.", 21, "alloy", 1.0)
    b = speech_cache.fingerprint("  Ich treffe mich\n  morgen.  ", 21, "alloy", 1.0)
    assert a == b


def test_andere_stimme_anderer_schluessel():
    a = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0)
    b = speech_cache.fingerprint("Ein Satz.", 21, "nova", 1.0)
    assert a != b


def test_anderer_anbieter_anderer_schluessel():
    a = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0)
    b = speech_cache.fingerprint("Ein Satz.", 22, "alloy", 1.0)
    assert a != b


def test_anderes_tempo_anderer_schluessel():
    a = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0)
    b = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.5)
    assert a != b


def test_teile_lassen_sich_nicht_ineinanderschieben():
    """Ohne Trennzeichen waeren ('ab', 1) und ('a', 'b1') derselbe Schluessel."""
    a = speech_cache.fingerprint("ab", 1, "x", 1.0)
    b = speech_cache.fingerprint("a", 1, "bx", 1.0)
    assert a != b


# --- der Vorrat im Sprechweg -------------------------------------------------

def test_erster_aufruf_spricht_und_legt_ab(settings, monkeypatch, vorrat):
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)

    assert speech.synthesize_sentence("Ein Satz.") == b"ID3-audio"
    assert len(client.aufrufe) == 1
    assert list(vorrat.inhalt.values()) == [b"ID3-audio"]


def test_zweiter_aufruf_kommt_aus_dem_vorrat(settings, monkeypatch):
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)

    speech.synthesize_sentence("Ein Satz.")
    assert speech.synthesize_sentence("Ein Satz.") == b"ID3-audio"
    # Der Anbieter wurde genau EINMAL gefragt, das ist der ganze Sinn der Sache.
    assert len(client.aufrufe) == 1


def test_der_vorrat_haengt_am_satz_nicht_an_der_karte(settings, monkeypatch):
    """Zwei verschiedene Karten mit demselben Beispielsatz teilen sich einen Ton, und
    ein neu erzeugter Kartensatz greift auf das zu, was ein alter schon gesprochen hat.
    Genau dafuer ist der Schluessel der Satz."""
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)

    speech.synthesize_sentence("Ich beschwere mich beim Chef.")
    speech.synthesize_sentence("  Ich beschwere mich\nbeim Chef.  ")
    assert len(client.aufrufe) == 1


def test_ein_anderer_satz_wird_neu_gesprochen(settings, monkeypatch):
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)

    speech.synthesize_sentence("Erster Satz.")
    speech.synthesize_sentence("Zweiter Satz.")
    assert len(client.aufrufe) == 2


def test_gesprochen_wird_der_normalisierte_text(settings, monkeypatch):
    """Sonst schickt der erste Aufruf etwas anderes zum Anbieter als das, was unter
    dem Schluessel abgelegt wird."""
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)

    speech.synthesize_sentence("  Ein\n  Satz.  ")
    assert client.aufrufe[0][0] == "Ein Satz."


def test_kaputter_vorrat_verhindert_das_vorlesen_nicht(settings, monkeypatch):
    """Der Vorrat ist eine Abkuerzung, keine Voraussetzung."""
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)
    _mit_vorrat(monkeypatch, _Vorrat(kaputt_beim_lesen=True, kaputt_beim_schreiben=True))

    assert speech.synthesize_sentence("Ein Satz.") == b"ID3-audio"


def test_ein_leerer_satz_wird_nicht_gesprochen(settings, monkeypatch):
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)

    with pytest.raises(HTTPException) as fehler:
        speech.synthesize_sentence("   \n  ")
    assert fehler.value.status_code == 503
    assert client.aufrufe == []


def test_ein_fehlschlag_legt_nichts_ab(settings, monkeypatch):
    """Sonst laege ein halber oder leerer Ton dauerhaft im Vorrat."""
    _eingerichtet(settings)
    client = _Client(fehler=2)
    _mit_client(monkeypatch, client)
    vorrat = _mit_vorrat(monkeypatch, _Vorrat())

    with pytest.raises(HTTPException):
        speech.synthesize_sentence("Ein Satz.")
    assert vorrat.inhalt == {}


def test_ein_modellwechsel_entwertet_den_vorrat():
    """Das Modell steht in der Route "Text in Sprache", nicht am Anbieter. Ginge es
    nicht in den Fingerabdruck ein, liefe der Vorrat nach einem Wechsel weiter mit dem
    alten Klang, und nichts wuerde ihn entwerten ausser neunzig Tagen Nichtnutzung."""
    alt = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0, "xtts-v2")
    neu = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0, "kokoro-v1")
    assert alt != neu


def test_der_sprechweg_nimmt_das_modell_in_den_schluessel(settings, monkeypatch, vorrat):
    """Nicht nur die Rechenfunktion kennt das Modell, der Weg reicht es auch durch."""
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)
    monkeypatch.setattr("src.dependencies.tts_model_for_provider", lambda pid: "modell-a")
    speech.synthesize_sentence("Ein Satz.")

    erwartet = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0, "modell-a")
    assert erwartet in vorrat.inhalt
