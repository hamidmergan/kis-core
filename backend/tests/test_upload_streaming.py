"""KI-Tutor upload concurrency cap.

The streaming itself now lives in ``src.utils.upload_stream`` and is covered by
test_tool_upload_streaming.py (shared with the classic tools). Was hier bleibt,
ist die Bremse für gleichzeitige Uploads.

Die war bis 2026-08 eine Admin-Einstellung. Das war die falsche Frage an den
falschen Adressaten: "wie viele Uploads gleichzeitig" hängt an Kernen und
Arbeitsspeicher, nicht an einer Meinung. Jetzt wird gemessen.
"""
from src.features.ai_assistant.routes.sources import _upload


def test_grenze_kommt_aus_der_erkannten_maschine():
    assert _upload._max_concurrent_uploads() == _upload.AIA_MAX_CONCURRENT_UPLOADS


def test_grenze_ist_nie_null():
    """0 hieße unbegrenzt. Genau das fror früher das Backend beim Hochladen ein,
    weil mehrere große Videos gleichzeitig durch Umwandlung und Ablage liefen."""
    assert _upload._max_concurrent_uploads() >= 1


def test_keine_einstellung_kann_die_bremse_mehr_aushebeln(monkeypatch):
    """Auch ein Eintrag in der Datenbank darf die Grenze nicht mehr verstellen."""
    monkeypatch.setattr(_upload.db, "get_setting", lambda *a, **k: "0")
    assert _upload._max_concurrent_uploads() >= 1
