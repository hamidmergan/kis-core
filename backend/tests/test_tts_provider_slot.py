"""Jede Vertonung braucht einen Platz beim Anbieter, egal ob Podcast, Vorlesen oder Screencast."""

from contextlib import contextmanager

from src.limits import TTS_PROVIDER_MAX_CONCURRENT
from src.services import openai_compat_tts


class _Antwort:
    status_code = 200
    content = b"mp3"
    text = ""


class _Client:
    def __init__(self, protokoll):
        self.protokoll = protokoll

    def post(self, url, json=None, headers=None):
        self.protokoll.append("post")
        return _Antwort()


def test_die_anfrage_laeuft_nur_mit_einem_platz(monkeypatch):
    protokoll = []

    @contextmanager
    def platz(provider, *, limit, wait_seconds):
        protokoll.append(("platz", provider, limit))
        yield
        protokoll.append("frei")

    monkeypatch.setattr(openai_compat_tts.provider_slots, "slot", platz)
    tts = openai_compat_tts.OpenAICompatTTSClient("https://models.mylab.example/v1", "tts-1", "k")

    assert tts._synthesize_one(_Client(protokoll), "Hallo", voice_id="nova") == b"mp3"
    assert protokoll == [("platz", "models.mylab.example", TTS_PROVIDER_MAX_CONCURRENT), "post", "frei"]
