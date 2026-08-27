"""Numbers are only spelled out when the language is known."""

import pytest

from src.services.openai_compat_tts import OpenAICompatTTSClient


class FakeResponse:
    status_code = 200
    content = b"mp3"
    text = ""


class FakeHttpClient:
    def __init__(self):
        self.payloads = []

    def post(self, url, json=None, headers=None):
        self.payloads.append(json)
        return FakeResponse()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def client_und_post(monkeypatch):
    fake = FakeHttpClient()
    monkeypatch.setattr("httpx.Client", lambda **kw: fake)
    return OpenAICompatTTSClient("https://tts.example/v1", model="xtts-v2"), fake


def test_englischer_screencast_bekommt_ausgeschriebene_zahlen(client_und_post):
    client, fake = client_und_post
    client.synthesize("The result was 47 percent.", "EN", voice_id="alloy")
    assert fake.payloads[0]["input"] == "The result was forty-seven percent."


def test_ohne_bekannte_sprache_bleiben_die_ziffern_stehen(client_und_post):
    """Guessing would be worse than digits, a wrong language sounds wrong."""
    client, fake = client_und_post
    client.synthesize("The result was 47 percent.", "", voice_id="alloy")
    assert fake.payloads[0]["input"] == "The result was 47 percent."


def test_synthesize_chunk_folgt_derselben_regel(client_und_post):
    client, fake = client_und_post
    client.synthesize_chunk("published in 1986.", voice_id="alloy", language="EN")
    assert fake.payloads[0]["input"] == "published in nineteen eighty-six."
    client.synthesize_chunk("published in 1986.", voice_id="alloy")
    assert fake.payloads[1]["input"] == "published in 1986."


def test_deutsche_texte_bleiben_wie_bisher(client_und_post):
    """The bug is measured for English only, so only there is anything touched."""
    client, fake = client_und_post
    client.synthesize_chunk("Es waren 47 Personen.", voice_id="alloy", language="DE")
    assert fake.payloads[0]["input"] == "Es waren 47 Personen."


def test_text_ohne_ziffern_geht_unveraendert_raus(client_und_post):
    client, fake = client_und_post
    client.synthesize("Hello everyone and welcome.", "EN", voice_id="alloy")
    assert fake.payloads[0]["input"] == "Hello everyone and welcome."
