"""The speech recognition route has to stream the upload to disk."""
import asyncio

import pytest
from fastapi import HTTPException

from src.limits import MAX_TRANSCRIPTION_BYTES
from src.routes import transcription as route


class _ChunkOnlyUpload:
    """UploadFile stand-in whose ``read()`` refuses to hand over everything."""

    def __init__(self, data: bytes, filename: str = "lecture.wav"):
        self.filename = filename
        self._data = data
        self._pos = 0

    async def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            raise AssertionError("unbounded read() would buffer the whole body in RAM")
        chunk = self._data[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


class _Request:
    def __init__(self, content_length: str | None = None):
        self.headers = {} if content_length is None else {"content-length": content_length}


def _wav(payload_size: int) -> bytes:
    return b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * payload_size


@pytest.fixture
def env(monkeypatch):
    """Silence the side effects and record what reaches storage / the queue."""
    stored: dict = {}
    queued: dict = {}

    def fake_save_from_path(user_id, job_uuid, ext, local_path):
        with open(local_path, "rb") as f:
            stored["bytes"] = f.read()
        stored["ext"] = ext
        return f"users/{user_id}/jobs/{job_uuid}/input{ext}"

    monkeypatch.setattr(route, "save_queue_file_from_path", fake_save_from_path, raising=False)
    monkeypatch.setattr(route.db, "create_job", lambda *a, **k: None)
    monkeypatch.setattr(route.db, "set_job_input_path", lambda *a, **k: None)
    monkeypatch.setattr(route, "enforce_tool_burst", lambda *a, **k: None)
    monkeypatch.setattr(route, "enforce_quota", lambda *a, **k: None)
    monkeypatch.setattr(route, "is_admin_user", lambda u: False)

    import src.tasks.general_tasks as gt

    class _Task:
        def delay(self, *a, **k):
            queued["args"] = a

    monkeypatch.setattr(gt, "run_transcribe", _Task())
    return stored, queued


def _call(upload, request=None):
    return asyncio.run(
        route.transcribe(
            request=request or _Request(),
            file=upload,
            task="transcribe",
            response_format="text",
            provider_id=None,
            current_user={"user_id": 42},
            locale="de",
        )
    )


def test_upload_reaches_storage_byte_for_byte_without_buffering(env):
    stored, queued = env
    data = _wav(300_000)

    result = _call(_ChunkOnlyUpload(data))

    assert result["status"] == "pending"
    assert stored["bytes"] == data      # nothing lost or truncated by the streaming
    assert stored["ext"] == ".wav"
    assert queued["args"]               # job actually handed to Celery


def test_empty_upload_is_rejected_before_a_job_is_queued(env):
    stored, queued = env

    with pytest.raises(HTTPException) as exc:
        _call(_ChunkOnlyUpload(b""))

    assert exc.value.status_code == 400
    assert queued == {}


def test_oversize_body_gets_413_and_queues_nothing(env):
    stored, queued = env
    monkey_size = MAX_TRANSCRIPTION_BYTES + 1

    with pytest.raises(HTTPException) as exc:
        _call(_ChunkOnlyUpload(_wav(0)), request=_Request(content_length=str(monkey_size)))

    assert exc.value.status_code == 413
    assert queued == {}


def test_content_not_matching_extension_is_rejected(env):
    """A renamed binary must not become a transcription job."""
    stored, queued = env

    with pytest.raises(HTTPException) as exc:
        _call(_ChunkOnlyUpload(b"MZ\x90\x00" + b"\x00" * 5000, filename="evil.wav"))

    assert exc.value.status_code == 400
    assert queued == {}
