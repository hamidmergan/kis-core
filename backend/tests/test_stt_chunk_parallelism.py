"""How many Whisper chunks go to the provider at once is an admin setting.

It used to be the hardcoded ``CHUNK_TRANSCRIBE_CONCURRENCY = 2``, chosen when
STT ran against GWDG and every extra parallel call risked a 429 for the whole
university. STT now runs elsewhere, and the right value depends on the provider
rather than on the code — so it moves to a setting, with the same guard rails as
``screencast_tts_parallelism``: a nonsense value falls back to the default, a
huge one is capped so a typo in the admin panel cannot flood the provider.
"""
import pytest

from src.limits import STT_CHUNK_DEFAULT_PARALLELISM, STT_CHUNK_MAX_PARALLELISM
from src.services.openai_compat_llm import _whisper_chunked


@pytest.fixture
def setting(monkeypatch):
    """Install a fake ``db.get_setting`` returning whatever the test sets."""
    holder = {"value": None}

    class _FakeDb:
        @staticmethod
        def get_setting(key, default=None):
            assert key == "stt_chunk_parallelism"
            return holder["value"] if holder["value"] is not None else default

    import src.database
    monkeypatch.setattr(src.database, "get_setting", _FakeDb.get_setting)
    return holder


def test_uses_the_configured_value(setting):
    setting["value"] = "6"
    assert _whisper_chunked.chunk_concurrency() == 6


def test_caps_an_oversized_value(setting):
    setting["value"] = str(STT_CHUNK_MAX_PARALLELISM * 10)
    assert _whisper_chunked.chunk_concurrency() == STT_CHUNK_MAX_PARALLELISM


@pytest.mark.parametrize("bad", ["0", "-3", "nonsense", ""])
def test_falls_back_to_the_default_on_unusable_values(setting, bad):
    setting["value"] = bad
    assert _whisper_chunked.chunk_concurrency() == STT_CHUNK_DEFAULT_PARALLELISM


def test_default_when_nothing_is_configured(setting):
    setting["value"] = None
    assert _whisper_chunked.chunk_concurrency() == STT_CHUNK_DEFAULT_PARALLELISM


def test_default_stays_conservative():
    """The shipped default must not raise provider load on its own; raising it
    is an explicit admin decision."""
    assert STT_CHUNK_DEFAULT_PARALLELISM == 2
