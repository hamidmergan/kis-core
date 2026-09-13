"""The finished transcript carries the AI notice, except in SRT (no comment syntax there)."""

import contextlib

import src.dependencies as deps
from src.services.ai_hinweis import AI_HINWEIS_TEXT
from src.tasks import general_tasks as gt


class _StubClient:
    def __init__(self, body: str):
        self.body = body

    def transcribe_chunked(self, *a, **k):
        return self.body

    def transcribe_and_translate_chunked(self, *a, **k):
        return self.body


def _run(monkeypatch, response_format: str, body: str) -> bytes:
    saved: dict = {}
    monkeypatch.setattr(gt.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)
    monkeypatch.setattr(gt, "delete_file", lambda p: None)
    monkeypatch.setattr(gt, "save_result_and_evict", lambda *a, **k: None)
    monkeypatch.setattr(gt, "save_result_file", lambda user_id, job_uuid, ext, data: saved.setdefault("bytes", data))
    monkeypatch.setattr(deps, "resolve_whisper_client", lambda pid=None: _StubClient(body))

    @contextlib.contextmanager
    def fake_open(path, suffix=""):
        yield f"/tmp/local{suffix}"

    @contextlib.contextmanager
    def fake_hb(job_uuid):
        yield

    monkeypatch.setattr(gt, "open_input_file", fake_open)
    monkeypatch.setattr(gt, "job_heartbeat", fake_hb)

    gt.run_transcribe.run.__func__(None, "job1", "ip", "clip.webm", "transcribe", response_format, None)
    return saved["bytes"]


def test_text_output_carries_the_notice(monkeypatch):
    result = _run(monkeypatch, "text", "Hallo")
    assert AI_HINWEIS_TEXT.encode("utf-8") in result


def test_vtt_output_carries_the_notice_as_a_note_block(monkeypatch):
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHallo\n"
    result = _run(monkeypatch, "vtt", vtt)
    assert b"NOTE\n" + AI_HINWEIS_TEXT.encode("utf-8") in result


def test_srt_output_stays_unmarked(monkeypatch):
    srt = "1\n00:00:00,000 --> 00:00:01,000\nHallo\n"
    result = _run(monkeypatch, "srt", srt)
    assert AI_HINWEIS_TEXT.encode("utf-8") not in result
