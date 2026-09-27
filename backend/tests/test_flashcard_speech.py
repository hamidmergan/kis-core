"""Which voice speaks the example sentence, both settings shipped empty."""

import pytest

from src.services import aia_flashcard_speech as speech


@pytest.fixture
def settings(monkeypatch):
    """The settings table as a dictionary, without a database."""
    werte: dict[str, str] = {}

    def get_setting(key, default=""):
        return werte.get(key, default)

    monkeypatch.setattr("src.database.get_setting", get_setting)
    return werte


@pytest.fixture(autouse=True)
def anbieter(monkeypatch):
    """The provider list, empty by default."""
    liste: list[dict] = []
    monkeypatch.setattr(
        "src.features.ai_providers.repository.providers.list_providers_with_capability",
        lambda capability: list(liste),
    )
    return liste


def test_ohne_einstellungen_ist_nichts_gewaehlt(settings):
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False


def test_nur_anbieter_reicht_nicht(settings):
    """A provider without a voice cannot speak, the button would do nothing."""
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
    """A broken setting must not crash, only leave the button out."""
    settings["aia_flashcard_voice_provider_id"] = "unsinn"
    settings["aia_flashcard_voice_id"] = "alloy"
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False


def test_null_als_anbieternummer_ist_ungueltig(settings):
    """Zero does not exist as a provider id, SERIAL starts at 1."""
    settings["aia_flashcard_voice_provider_id"] = "0"
    settings["aia_flashcard_voice_id"] = "alloy"
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False


def test_negative_anbieternummer_ist_ungueltig(settings):
    """Negative numbers do not exist as provider ids."""
    settings["aia_flashcard_voice_provider_id"] = "-5"
    settings["aia_flashcard_voice_id"] = "alloy"
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False


# --- the speaking itself -----------------------------------------------------

from fastapi import HTTPException


class _Client:
    """A provider that throws the first ``fehler`` attempts and then delivers."""

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
    """A second attempt catches a single refusal from the provider."""
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"
    client = _Client(fehler=1)
    _mit_client(monkeypatch, client)

    assert speech.synthesize_sentence("Ein Satz.") == b"ID3-audio"
    assert len(client.aufrufe) == 2


def test_zwei_fehlschlaege_ergeben_503(settings, monkeypatch):
    """No third attempt, the learner would wait too long."""
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"
    client = _Client(fehler=2)
    _mit_client(monkeypatch, client)

    with pytest.raises(HTTPException) as fehler:
        speech.synthesize_sentence("Ein Satz.")
    assert fehler.value.status_code == 503
    assert len(client.aufrufe) == 2


def test_kein_anbieter_hinter_der_nummer_gibt_503(settings, monkeypatch):
    """The id points at a deleted or disabled provider."""
    settings["aia_flashcard_voice_provider_id"] = "999"
    settings["aia_flashcard_voice_id"] = "alloy"
    monkeypatch.setattr(
        "src.dependencies.get_tts_client_for_provider", lambda pid: None
    )
    with pytest.raises(HTTPException) as fehler:
        speech.synthesize_sentence("Ein Satz.")
    assert fehler.value.status_code == 503


def test_abholt_fehler_gibt_503_kein_absturz(settings, monkeypatch):
    """An error while resolving becomes a 503, not a crash."""
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"

    def _wirft_runtime_error(pid):
        raise RuntimeError("Modell nicht konfiguriert")

    monkeypatch.setattr("src.dependencies.get_tts_client_for_provider", _wirft_runtime_error)
    with pytest.raises(HTTPException) as fehler:
        speech.synthesize_sentence("Ein Satz.")
    assert fehler.value.status_code == 503


# The key hangs off the sentence, and a broken pool prevents nothing.

from src.features.ai_assistant.repository import speech_cache


class _Vorrat:
    """The pool as a dictionary, without a database."""

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
    """The pool as a dictionary, otherwise the tests poison each other."""
    return _mit_vorrat(monkeypatch, _Vorrat())


def _mit_vorrat(monkeypatch, vorrat):
    monkeypatch.setattr(speech_cache, "get", vorrat.get)
    monkeypatch.setattr(speech_cache, "put", vorrat.put)
    return vorrat


@pytest.fixture(autouse=True)
def tts_modell(monkeypatch):
    """The model from the route, otherwise every speaking test fails."""
    monkeypatch.setattr("src.dependencies.tts_model_for_provider", lambda _pid: "")


@pytest.fixture(autouse=True)
def stimmwahl(monkeypatch):
    """The configured provider is there, otherwise the choice would ask the real database and network."""
    from src.services import tts_job_provider

    monkeypatch.setattr(tts_job_provider, "pick",
                        lambda pid, voices: tts_job_provider.VoicePick(pid, tuple(voices), False))


def _eingerichtet(settings):
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "alloy"


# --- the fingerprint ---------------------------------------------------------

def test_derselbe_satz_ergibt_denselben_schluessel():
    a = speech_cache.fingerprint("Ich treffe mich morgen.", 21, "alloy", 1.0)
    b = speech_cache.fingerprint("Ich treffe mich morgen.", 21, "alloy", 1.0)
    assert a == b


def test_zeilenumbrueche_und_randleerzeichen_aendern_den_schluessel_nicht():
    """If this normalises differently from the provider, the pool never hits."""
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
    """Without a separator ('ab', 1) and ('a', 'b1') would be the same key."""
    a = speech_cache.fingerprint("ab", 1, "x", 1.0)
    b = speech_cache.fingerprint("a", 1, "bx", 1.0)
    assert a != b


# --- the pool on the speaking path -------------------------------------------

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
    # The provider was asked exactly ONCE, that is the whole point.
    assert len(client.aufrufe) == 1


def test_der_vorrat_haengt_am_satz_nicht_an_der_karte(settings, monkeypatch):
    """Two cards with the same example sentence share one audio file."""
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
    """Otherwise something else goes to the provider than what sits under the key."""
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)

    speech.synthesize_sentence("  Ein\n  Satz.  ")
    assert client.aufrufe[0][0] == "Ein Satz."


def test_kaputter_vorrat_verhindert_das_vorlesen_nicht(settings, monkeypatch):
    """The pool is a shortcut, not a requirement."""
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
    """Otherwise a half or empty audio file would sit in the pool for good."""
    _eingerichtet(settings)
    client = _Client(fehler=2)
    _mit_client(monkeypatch, client)
    vorrat = _mit_vorrat(monkeypatch, _Vorrat())

    with pytest.raises(HTTPException):
        speech.synthesize_sentence("Ein Satz.")
    assert vorrat.inhalt == {}


def test_ein_modellwechsel_entwertet_den_vorrat():
    """Without the model in the fingerprint the old sound would stay after a switch."""
    alt = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0, "xtts-v2")
    neu = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0, "stimme-v1")
    assert alt != neu


def test_der_sprechweg_nimmt_das_modell_in_den_schluessel(settings, monkeypatch, vorrat):
    """Not only the computing function knows the model, the path passes it through too."""
    _eingerichtet(settings)
    client = _Client()
    _mit_client(monkeypatch, client)
    monkeypatch.setattr("src.dependencies.tts_model_for_provider", lambda pid: "modell-a")
    speech.synthesize_sentence("Ein Satz.")

    erwartet = speech_cache.fingerprint("Ein Satz.", 21, "alloy", 1.0, "modell-a")
    assert erwartet in vorrat.inhalt


# Nothing chosen now means the first voice of the list.

def _anbieter(pid, name, *stimmen):
    return {"id": pid, "name": name,
            "voices": [{"voice_id": s, "name": s.title()} for s in stimmen]}


def test_ohne_wahl_gilt_die_erste_stimme(settings, anbieter):
    anbieter.append(_anbieter(21, "THL myLab", "alloy", "echo"))
    assert speech.configured_voice() == (21, "alloy")
    assert speech.speech_enabled() is True


def test_die_reihenfolge_der_anbieterliste_entscheidet(settings, anbieter):
    """The same order as in the admin dropdown."""
    anbieter.extend([
        _anbieter(22, "Erster", "aaa"),
        _anbieter(21, "Zweiter", "bbb"),
    ])
    assert speech.configured_voice() == (22, "aaa")


def test_ein_anbieter_ohne_stimmen_wird_uebersprungen(settings, anbieter):
    anbieter.extend([
        _anbieter(30, "Ohne Stimmen"),
        _anbieter(31, "Mit Stimmen", "nova"),
    ])
    assert speech.configured_voice() == (31, "nova")


def test_die_ausdrueckliche_wahl_schlaegt_den_rueckfall(settings, anbieter):
    anbieter.append(_anbieter(21, "THL myLab", "alloy", "echo"))
    settings["aia_flashcard_voice_provider_id"] = "21"
    settings["aia_flashcard_voice_id"] = "echo"
    assert speech.configured_voice() == (21, "echo")


def test_eine_kaputte_wahl_faellt_auf_die_erste_stimme_zurueck(settings, anbieter):
    """A broken setting falls back to the default."""
    anbieter.append(_anbieter(21, "THL myLab", "alloy"))
    settings["aia_flashcard_voice_provider_id"] = "unsinn"
    settings["aia_flashcard_voice_id"] = "echo"
    assert speech.configured_voice() == (21, "alloy")


def test_ohne_jeden_anbieter_bleibt_es_still(settings, anbieter):
    """No enabled provider with voices means nobody can speak."""
    assert speech.configured_voice() is None
    assert speech.speech_enabled() is False
