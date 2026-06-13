"""run_transcribe retry policy: a 429 requeues with backoff (resume via cache); any
other error or an exhausted retry budget marks the job failed. Mirrors the AIA
media-ingestion policy and matches the "only 429 is retried" decision."""
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
    """No-op the side effects so the task body runs straight to the except branch.

    Returns ``(set_error, failed)``: ``set_error(msg)`` installs a whisper client that
    raises ``msg`` (monkeypatched, so it is restored after the test), ``failed`` records
    a ``_handle_task_exception`` call."""
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
    set_error("Chunk 1 transcription failed: Whisper API error (KISSKI): Error code: 429 - rate limit")
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


def test_non_rate_limit_error_fails_immediately(env):
    set_error, failed = env
    set_error("Chunk 1 transcription failed: Whisper API error (KISSKI): Internal Server Error")
    s = _FakeSelf(retries=0)
    with pytest.raises(RuntimeError):
        _run(s)
    assert s.retry_calls == []          # a 500 is NOT auto-retried (only 429)
    assert failed.get("label") == "Transcribe"
