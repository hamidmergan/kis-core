"""The per-part progress reaches the job row."""
import contextlib

import pytest

from src.services.openai_compat_llm import _whisper_chunked as wc
from src.tasks import general_tasks as gt


class _StubWhisper(wc._WhisperChunkedMixin):
    def transcribe(self, path: str, response_format: str = "text") -> str:
        return "text"

    def transcribe_and_translate(self, path: str, response_format: str = "text") -> str:
        return "text"


@pytest.fixture
def four_chunks(monkeypatch):
    """Deterministic 4-chunk split, serial, no ffmpeg/Redis."""
    monkeypatch.setattr(wc, "chunk_concurrency", lambda: 1)
    monkeypatch.setattr(wc, "get_audio_duration", lambda p: 2000.0)
    monkeypatch.setattr(wc, "find_silence_starts", lambda p: [])
    monkeypatch.setattr(wc, "compute_split_points", lambda d, s: [540.0, 1080.0, 1620.0])
    monkeypatch.setattr(
        wc, "split_audio",
        lambda fp, sp, tmp: [(f"{tmp}/chunk_{i:03d}.mp3", i * 540.0) for i in range(len(sp) + 1)],
    )


def test_reports_every_chunk_exactly_once(four_chunks):
    seen: list[tuple[int, int]] = []
    _StubWhisper().transcribe_chunked("f.webm", on_progress=lambda done, total: seen.append((done, total)))

    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_translate_mode_reports_too(four_chunks):
    seen: list[tuple[int, int]] = []
    _StubWhisper().transcribe_and_translate_chunked(
        "f.webm", on_progress=lambda done, total: seen.append((done, total))
    )

    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_short_audio_is_not_split_and_reports_nothing(four_chunks, monkeypatch):
    """Under the chunk ceiling there is one API call and no progress to report."""
    monkeypatch.setattr(wc, "get_audio_duration", lambda p: 60.0)
    monkeypatch.setattr(wc, "fits_single_upload", lambda p, d: True)
    seen: list[tuple[int, int]] = []

    _StubWhisper().transcribe_chunked("f.webm", on_progress=lambda d, t: seen.append((d, t)))

    assert seen == []


def test_no_callback_still_works(four_chunks):
    """The AIA path passes no callback; it must not crash."""
    assert _StubWhisper().transcribe_chunked("f.webm") == "text text text text"


# --- the task wires the callback to the job row ------------------------------

def test_task_writes_chunk_progress_to_the_job(monkeypatch):
    updates: list[dict] = []

    monkeypatch.setattr(
        gt.db, "update_job_status",
        lambda job_uuid, status, progress=None, **k: updates.append({"status": status, "progress": progress}),
    )
    monkeypatch.setattr(gt.db, "set_job_input_path", lambda *a, **k: None)
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)
    monkeypatch.setattr(gt, "save_result_file", lambda *a, **k: "/res.txt")
    monkeypatch.setattr(gt, "save_result_and_evict", lambda *a, **k: None)
    monkeypatch.setattr(gt, "delete_file", lambda *a, **k: None)

    @contextlib.contextmanager
    def fake_open(path, suffix=""):
        yield f"/tmp/local{suffix}"

    @contextlib.contextmanager
    def fake_hb(job_uuid):
        yield

    monkeypatch.setattr(gt, "open_input_file", fake_open)
    monkeypatch.setattr(gt, "job_heartbeat", fake_hb)

    class _Client:
        def transcribe_chunked(self, path, response_format="text", cache_key=None, on_progress=None):
            on_progress(1, 3)
            on_progress(2, 3)
            on_progress(3, 3)
            return "done"

    import src.dependencies as deps
    monkeypatch.setattr(deps, "resolve_whisper_client", lambda pid=None: _Client())

    gt.run_transcribe.run.__func__(
        object(), "job1", "ip", "VL.webm", "transcribe", "text", None
    )

    chunk_updates = [u["progress"] for u in updates if u["progress"]]
    assert chunk_updates == [
        {"step": "transcribe", "current": 1, "total": 3},
        {"step": "transcribe", "current": 2, "total": 3},
        {"step": "transcribe", "current": 3, "total": 3},
    ]
