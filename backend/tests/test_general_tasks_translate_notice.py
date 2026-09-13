"""Translated .txt files carry the AI notice; structured formats stay untouched."""

import contextlib

from src.services.ai_hinweis import AI_HINWEIS_TEXT
from src.tasks import general_tasks as gt


class _StubService:
    def __init__(self, *a, **k):
        pass

    def translate_filename(self, filename, source_lang, target_lang):
        return filename

    def translate_text(self, text, source_lang, target_lang):
        return "Translated body"


def _run(monkeypatch, filename: str, content: bytes) -> bytes:
    saved: dict = {}
    monkeypatch.setattr(gt.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)
    monkeypatch.setattr(gt, "get_file", lambda p: content)
    monkeypatch.setattr(gt, "delete_file", lambda p: None)
    monkeypatch.setattr(gt, "save_result_and_evict", lambda *a, **k: None)
    monkeypatch.setattr(gt, "save_result_file", lambda user_id, job_uuid, ext, data: saved.setdefault("bytes", data))
    monkeypatch.setattr(gt, "get_translate_client_for_provider", lambda pid, glossary_entries=None: (object(), {}))
    monkeypatch.setattr(gt, "TranslationService", _StubService)

    @contextlib.contextmanager
    def fake_hb(job_uuid):
        yield

    monkeypatch.setattr(gt, "job_heartbeat", fake_hb)

    gt.run_translate.run.__func__(None, "job1", "ip", filename, "{}", "de", "en")
    return saved["bytes"]


def test_txt_output_carries_the_notice(monkeypatch):
    assert AI_HINWEIS_TEXT.encode("utf-8") in _run(monkeypatch, "doc.txt", b"Body")
