"""The generated summary carries the AI notice as a leading line."""

import contextlib

from src.services.ai_hinweis import AI_HINWEIS_TEXT
from src.tasks import general_tasks as gt

_LONG_ENOUGH_TEXT = (
    b"Enough words to pass the minimum word count check here easily today "
    b"with several more words added just to be safe and sure."
)


class _StubLLMClient:
    def generate_summary(self, text):
        return "Kurze Zusammenfassung."


def test_summary_output_carries_the_notice(monkeypatch):
    saved: dict = {}
    monkeypatch.setattr(gt.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(gt.db, "get_job", lambda j: {"creator_locale": "de"})
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)
    monkeypatch.setattr(gt, "get_file", lambda p: _LONG_ENOUGH_TEXT)
    monkeypatch.setattr(gt, "delete_file", lambda p: None)
    monkeypatch.setattr(gt, "save_result_and_evict", lambda *a, **k: None)
    monkeypatch.setattr(gt, "save_result_file", lambda user_id, job_uuid, ext, data: saved.setdefault("bytes", data))
    monkeypatch.setattr(gt, "_get_llm_client", lambda pid=None: _StubLLMClient())

    @contextlib.contextmanager
    def fake_hb(job_uuid):
        yield

    monkeypatch.setattr(gt, "job_heartbeat", fake_hb)

    gt.run_summary.run.__func__(None, "job1", "input.txt", "input.txt", None)

    assert AI_HINWEIS_TEXT.encode("utf-8") in saved["bytes"]
