"""Every temporary disruption re-queues, a permanent one fails right away."""
import contextlib

import pytest

from src.tasks import general_tasks as gt


class _Req:
    def __init__(self, retries):
        self.retries = retries


class _Retrying(Exception):
    """Stand-in for celery's Retry, so we can assert self.retry fired and stop."""


class _FakeSelf:
    def __init__(self, retries=0):
        self.request = _Req(retries)
        self.retry_calls: list[tuple] = []

    def retry(self, exc=None, countdown=None, max_retries=None):
        self.retry_calls.append((countdown, max_retries))
        raise _Retrying()


class _RaisingClient:
    def __init__(self, msg):
        self.msg = msg

    def transcribe_chunked(self, *a, **k):
        raise RuntimeError(self.msg)

    def transcribe_and_translate_chunked(self, *a, **k):
        raise RuntimeError(self.msg)


@pytest.fixture
def env(monkeypatch):
    """Silences the side effects so the job runs into the error branch."""
    import src.dependencies as deps

    monkeypatch.setattr(gt.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)

    @contextlib.contextmanager
    def fake_open(path, suffix=""):
        yield f"/tmp/local{suffix}"

    @contextlib.contextmanager
    def fake_hb(job_uuid):
        yield

    monkeypatch.setattr(gt, "open_input_file", fake_open)
    monkeypatch.setattr(gt, "job_heartbeat", fake_hb)

    failed: dict = {}
    monkeypatch.setattr(gt, "_handle_task_exception",
                        lambda j, e, task_label=None: failed.update({"err": str(e), "label": task_label}))

    def set_error(msg):
        monkeypatch.setattr(deps, "resolve_whisper_client", lambda pid=None: _RaisingClient(msg))

    return set_error, failed


def _run(self_obj):
    # Call the raw function with our fake self (bypass Celery's bound-method self).
    return gt.run_transcribe.run.__func__(
        self_obj, "job1", "ip", "VL.webm", "transcribe", "text", None
    )


def test_429_requeues_with_backoff_not_failed(env):
    set_error, failed = env
    set_error("Chunk 1 transcription failed: Whisper API error (Anbieter A): Error code: 429 - rate limit")
    s = _FakeSelf(retries=0)
    with pytest.raises(_Retrying):
        _run(s)
    assert s.retry_calls == [(30, 5)]   # first backoff 30s, max 5 retries
    assert failed == {}                 # NOT marked failed while retrying


def test_429_after_max_retries_marks_failed(env):
    set_error, failed = env
    set_error("Error code: 429 - API rate limit exceeded")
    s = _FakeSelf(retries=5)            # budget already spent
    with pytest.raises(RuntimeError):
        _run(s)
    assert s.retry_calls == []          # no further retry
    assert failed.get("label") == "Transcribe"


@pytest.mark.parametrize("msg", [
    "Chunk 1 transcription failed: Whisper API error (Anbieter A): Internal Server Error",
    "Chunk 9 transcription failed: Whisper API error (myLab): Bad Gateway",
    "Whisper API error (myLab): Service Unavailable",
    "Whisper API error (myLab): Read timeout",
    "Whisper API error (myLab): Connection reset by peer",
])
def test_transient_upstream_failure_requeues_instead_of_losing_finished_chunks(env, msg):
    set_error, failed = env
    set_error(msg)
    s = _FakeSelf(retries=0)
    with pytest.raises(_Retrying):
        _run(s)
    assert s.retry_calls == [(30, 5)]
    assert failed == {}


def test_transient_failure_after_max_retries_marks_failed(env):
    set_error, failed = env
    set_error("Whisper API error (myLab): Bad Gateway")
    s = _FakeSelf(retries=5)
    with pytest.raises(RuntimeError):
        _run(s)
    assert s.retry_calls == []
    assert failed.get("label") == "Transcribe"


@pytest.mark.parametrize("msg", [
    "Audio zu lang (183.4 min). Maximum: 100 Minuten.",
    "ffprobe failed: Invalid data found when processing input",
    "Whisper returned no output",
])
def test_permanent_failure_is_not_retried(env, msg):
    """Retrying these burns the backoff budget and still fails. Fail loudly instead."""
    set_error, failed = env
    set_error(msg)
    s = _FakeSelf(retries=0)
    with pytest.raises(RuntimeError):
        _run(s)
    assert s.retry_calls == []
    assert failed.get("label") == "Transcribe"
