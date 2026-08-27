"""The brake on concurrent uploads is measured instead of configured."""
from src.features.ai_assistant.routes.sources import _upload


def test_grenze_kommt_aus_der_erkannten_maschine():
    assert _upload._max_concurrent_uploads() == _upload.AIA_MAX_CONCURRENT_UPLOADS


def test_grenze_ist_nie_null():
    """0 would mean unlimited and used to freeze the backend."""
    assert _upload._max_concurrent_uploads() >= 1


def test_keine_einstellung_kann_die_bremse_mehr_aushebeln(monkeypatch):
    """An entry in the database must no longer move the limit either."""
    monkeypatch.setattr(_upload.db, "get_setting", lambda *a, **k: "0")
    assert _upload._max_concurrent_uploads() >= 1
