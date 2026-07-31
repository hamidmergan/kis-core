"""KI-Tutor upload concurrency cap.

The streaming itself now lives in ``src.utils.upload_stream`` and is covered by
test_tool_upload_streaming.py (shared with the classic tools). What stays
KI-Tutor specific is the admin-tunable ``aia_max_concurrent_uploads`` setting.
"""
from src.features.ai_assistant.routes.sources import _upload


def test_max_concurrent_uploads_reads_and_clamps(monkeypatch):
    monkeypatch.setattr(_upload.db, "get_setting", lambda *a, **k: "5")
    assert _upload._max_concurrent_uploads() == 5
    # 0 means unlimited and must be preserved.
    monkeypatch.setattr(_upload.db, "get_setting", lambda *a, **k: "0")
    assert _upload._max_concurrent_uploads() == 0
    # Negative is clamped to 0.
    monkeypatch.setattr(_upload.db, "get_setting", lambda *a, **k: "-4")
    assert _upload._max_concurrent_uploads() == 0
    # Garbage falls back to the code default.
    monkeypatch.setattr(_upload.db, "get_setting", lambda *a, **k: "nonsense")
    assert _upload._max_concurrent_uploads() == _upload.AIA_MAX_CONCURRENT_UPLOADS
