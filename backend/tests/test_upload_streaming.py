"""Upload streaming + global concurrency cap.

Covers the low-RAM upload path: the request body is streamed to a temp file in
chunks (never held fully in memory), the first 64 KiB is kept for content
validation, an oversize body is rejected mid-stream, and the admin-tunable
``aia_max_concurrent_uploads`` setting is read/clamped correctly.
"""
import asyncio
import os

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes.sources import _upload


class _FakeUpload:
    """Minimal UploadFile stand-in with an async chunked ``read``."""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    async def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


def test_stream_writes_file_and_keeps_head(tmp_path):
    data = b"%PDF-1.7\n" + b"x" * 200_000
    dest = str(tmp_path / "out.bin")
    total, head = asyncio.run(
        _upload._stream_to_tempfile(_FakeUpload(data), dest, max_bytes=10 * 1024 * 1024, locale="de")
    )
    assert total == len(data)
    assert os.path.getsize(dest) == len(data)
    # Head is exactly the first 64 KiB and starts with the real bytes.
    assert len(head) == 65536
    assert head.startswith(b"%PDF-1.7")


def test_stream_small_file_head_is_whole_file(tmp_path):
    data = b"hello world"
    dest = str(tmp_path / "small.txt")
    total, head = asyncio.run(
        _upload._stream_to_tempfile(_FakeUpload(data), dest, max_bytes=1024, locale="de")
    )
    assert total == len(data)
    assert head == data


def test_stream_rejects_oversize_midstream(tmp_path):
    data = b"x" * (3 * 1024 * 1024)
    dest = str(tmp_path / "big.bin")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            _upload._stream_to_tempfile(_FakeUpload(data), dest, max_bytes=1 * 1024 * 1024, locale="de")
        )
    assert exc.value.status_code == 413


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
