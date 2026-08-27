"""The preview of a voice comes from the cache once it has been spoken."""

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.repository import speech_cache
from src.services import tts_voice_preview as vorschau


class _Client:
    """A provider that records what it was asked for."""

    def __init__(self, erreichbar=True, wirft=False):
        self.erreichbar = erreichbar
        self.wirft = wirft
        self.aufrufe = []
        self.erreichbarkeitsfragen = 0

    def is_available(self):
        self.erreichbarkeitsfragen += 1
        return self.erreichbar

    def synthesize_chunk(self, text, *, voice_id, speed=1.0, **kwargs):
        self.aufrufe.append((text, voice_id, speed))
        if self.wirft:
            raise RuntimeError("TTS API error (500): Internal Server Error")
        return b"ID3-audio"


class _Vorrat:
    """The cache as a dictionary, without a database."""

    def __init__(self, kaputt_beim_lesen=False, kaputt_beim_schreiben=False):
        self.inhalt = {}
        self.kaputt_beim_lesen = kaputt_beim_lesen
        self.kaputt_beim_schreiben = kaputt_beim_schreiben

    def get(self, key):
        if self.kaputt_beim_lesen:
            raise RuntimeError("Datenbank weg")
        return self.inhalt.get(key)

    def put(self, key, audio):
        if self.kaputt_beim_schreiben:
            raise RuntimeError("Datenbank weg")
        self.inhalt[key] = audio


@pytest.fixture(autouse=True)
def vorrat(monkeypatch):
    """The cache as a dictionary, otherwise a test would write to the real database."""
    return _mit_vorrat(monkeypatch, _Vorrat())


def _mit_vorrat(monkeypatch, v):
    monkeypatch.setattr(speech_cache, "get", v.get)
    monkeypatch.setattr(speech_cache, "put", v.put)
    return v


@pytest.fixture(autouse=True)
def sprachen(monkeypatch):
    """The language of a voice, without a database, German by default."""
    zuordnung: dict[str, str] = {}
    monkeypatch.setattr(
        "src.dependencies._voice_language_for",
        lambda pid, vid: zuordnung.get(vid, "de"),
    )
    return zuordnung


@pytest.fixture(autouse=True)
def tts_modell(monkeypatch):
    """The model from the text-to-speech route, without a database."""
    monkeypatch.setattr("src.dependencies.tts_model_for_provider", lambda _pid: "")


def _mit_client(monkeypatch, client):
    monkeypatch.setattr("src.dependencies.get_tts_client_for_provider", lambda pid: client)
    return client


# --- the cache on the preview path -------------------------------------------

def test_erster_aufruf_spricht_und_legt_ab(monkeypatch, vorrat):
    client = _mit_client(monkeypatch, _Client())

    assert vorschau.preview_audio(21, "alloy") == b"ID3-audio"
    assert len(client.aufrufe) == 1
    assert list(vorrat.inhalt.values()) == [b"ID3-audio"]


def test_zweiter_aufruf_kommt_aus_dem_vorrat(monkeypatch):
    client = _mit_client(monkeypatch, _Client())

    vorschau.preview_audio(21, "alloy")
    assert vorschau.preview_audio(21, "alloy") == b"ID3-audio"
    assert len(client.aufrufe) == 1


def test_ein_treffer_fasst_den_anbieter_gar_nicht_an(monkeypatch):
    """A hit takes no network trip, not even for the reachability question."""
    client = _mit_client(monkeypatch, _Client())
    vorschau.preview_audio(21, "alloy")
    vorher = client.erreichbarkeitsfragen

    vorschau.preview_audio(21, "alloy")
    assert client.erreichbarkeitsfragen == vorher


def test_eine_andere_stimme_wird_neu_gesprochen(monkeypatch):
    client = _mit_client(monkeypatch, _Client())

    vorschau.preview_audio(21, "alloy")
    vorschau.preview_audio(21, "nova")
    assert len(client.aufrufe) == 2


def test_ein_anderer_anbieter_wird_neu_gesprochen(monkeypatch):
    client = _mit_client(monkeypatch, _Client())

    vorschau.preview_audio(21, "alloy")
    vorschau.preview_audio(22, "alloy")
    assert len(client.aufrufe) == 2


def test_das_tempo_ist_eins(monkeypatch):
    """Goes into the fingerprint, a change invalidates the cache."""
    client = _mit_client(monkeypatch, _Client())
    vorschau.preview_audio(21, "alloy")
    assert client.aufrufe[0][2] == 1.0


# --- the language of the preview sentence ------------------------------------

def test_eine_englische_stimme_bekommt_den_englischen_satz(monkeypatch, sprachen):
    sprachen["nova"] = "en"
    client = _mit_client(monkeypatch, _Client())

    vorschau.preview_audio(21, "nova")
    assert client.aufrufe[0][0].startswith("Hello!")


def test_eine_deutsche_stimme_bekommt_den_deutschen_satz(monkeypatch):
    client = _mit_client(monkeypatch, _Client())

    vorschau.preview_audio(21, "alloy")
    assert client.aufrufe[0][0].startswith("Hallo!")


def test_ohne_stimme_entscheidet_die_oberflaechensprache(monkeypatch):
    """Without a voice there is nothing to derive a language from."""
    client = _mit_client(monkeypatch, _Client())

    vorschau.preview_audio(21, "", locale="en")
    assert client.aufrufe[0][0].startswith("Hello!")


def test_die_sprache_kommt_aus_der_datenbank_nicht_vom_aufrufer(monkeypatch, sprachen):
    """Otherwise the browser could decide the language and with it the key."""
    sprachen["nova"] = "en"
    client = _mit_client(monkeypatch, _Client())

    vorschau.preview_audio(21, "nova", locale="de")
    assert client.aufrufe[0][0].startswith("Hello!")


# --- the model in the key ----------------------------------------------------

def test_der_vorschau_weg_nimmt_das_modell_in_den_schluessel(monkeypatch, vorrat):
    """Without the model in the key the cache returns the old sound after a switch."""
    _mit_client(monkeypatch, _Client())
    monkeypatch.setattr("src.dependencies.tts_model_for_provider", lambda pid: "modell-a")

    vorschau.preview_audio(21, "alloy")

    erwartet = speech_cache.fingerprint(
        vorschau.preview_text("de"), 21, "alloy", 1.0, "modell-a")
    assert erwartet in vorrat.inhalt


def test_ein_modellwechsel_spricht_neu(monkeypatch):
    client = _mit_client(monkeypatch, _Client())

    monkeypatch.setattr("src.dependencies.tts_model_for_provider", lambda pid: "modell-a")
    vorschau.preview_audio(21, "alloy")
    monkeypatch.setattr("src.dependencies.tts_model_for_provider", lambda pid: "modell-b")
    vorschau.preview_audio(21, "alloy")

    assert len(client.aufrufe) == 2


# --- when something is broken ------------------------------------------------

def test_kaputter_vorrat_verhindert_die_vorschau_nicht(monkeypatch):
    """The cache is a shortcut, not a requirement."""
    client = _mit_client(monkeypatch, _Client())
    _mit_vorrat(monkeypatch, _Vorrat(kaputt_beim_lesen=True, kaputt_beim_schreiben=True))

    assert vorschau.preview_audio(21, "alloy") == b"ID3-audio"
    assert len(client.aufrufe) == 1


def test_ein_fehlschlag_legt_nichts_ab(monkeypatch, vorrat):
    """An empty audio file in the cache would silence the voice for good."""
    _mit_client(monkeypatch, _Client(wirft=True))

    with pytest.raises(RuntimeError):
        vorschau.preview_audio(21, "alloy")
    assert vorrat.inhalt == {}


def test_unerreichbarer_anbieter_gibt_503(monkeypatch):
    _mit_client(monkeypatch, _Client(erreichbar=False))

    with pytest.raises(HTTPException) as fehler:
        vorschau.preview_audio(21, "alloy")
    assert fehler.value.status_code == 503


def test_kein_anbieter_hinter_der_nummer_gibt_503(monkeypatch):
    _mit_client(monkeypatch, None)

    with pytest.raises(HTTPException) as fehler:
        vorschau.preview_audio(999, "alloy")
    assert fehler.value.status_code == 503


def test_fehlendes_modell_gibt_503_kein_absturz(monkeypatch):
    """get_tts_client_for_provider raises when the route has no model stored."""
    def _wirft(pid):
        raise RuntimeError("tts route has no model_name")

    monkeypatch.setattr("src.dependencies.get_tts_client_for_provider", _wirft)
    with pytest.raises(HTTPException) as fehler:
        vorschau.preview_audio(21, "alloy")
    assert fehler.value.status_code == 503


def test_ein_treffer_ueberlebt_einen_toten_anbieter(monkeypatch, vorrat):
    """The cache is asked before the provider, so a known audio arrives without it."""
    _mit_client(monkeypatch, _Client())
    vorschau.preview_audio(21, "alloy")

    _mit_client(monkeypatch, None)
    assert vorschau.preview_audio(21, "alloy") == b"ID3-audio"
