"""Concurrent provider requests are fixed measured constants."""

from src.limits import SCREENCAST_TTS_PARALLELISM, STT_CHUNK_PARALLELISM
from src.services.openai_compat_llm import _whisper_chunked
from src.services.screencast import generation


def test_vertonung_nimmt_den_gemessenen_wert():
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_PARALLELISM


def test_spracherkennung_nimmt_den_gemessenen_wert():
    assert _whisper_chunked.chunk_concurrency() == STT_CHUNK_PARALLELISM


def test_keine_einstellung_kann_die_werte_mehr_verstellen(monkeypatch):
    """Old entries in the database must have no effect any more."""
    from src import database as db

    monkeypatch.setattr(db, "get_setting", lambda *a, **k: "99")
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_PARALLELISM
    assert _whisper_chunked.chunk_concurrency() == STT_CHUNK_PARALLELISM


def test_vertonung_laeuft_nicht_einzeln():
    """The old value made a long lecture impossible."""
    assert SCREENCAST_TTS_PARALLELISM > 1


def test_spracherkennung_bleibt_zurueckhaltend():
    """The value stays in a measured, restrained range."""
    assert 1 <= STT_CHUNK_PARALLELISM <= 4
