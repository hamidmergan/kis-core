"""Generated and edited images carry the AI notice as a PNG text chunk."""

import base64
import contextlib
import io

from PIL import Image

from src.services.ai_hinweis import AI_HINWEIS_TEXT
from src.tasks import general_tasks as gt


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "PNG")
    return buf.getvalue()


class _StubResponse:
    def __init__(self, status_code, data=None, headers=None, content=b""):
        self.status_code = status_code
        self._data = data
        self.headers = headers or {}
        self.content = content

    def json(self):
        return self._data


class _StubImageClient:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, *a, **k):
        return self._response


@contextlib.contextmanager
def _fake_hb(job_uuid):
    yield


def _base_mocks(monkeypatch, saved: dict):
    monkeypatch.setattr(gt.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)
    monkeypatch.setattr(gt, "delete_file", lambda p: None)
    monkeypatch.setattr(gt, "save_result_and_evict", lambda *a, **k: None)
    monkeypatch.setattr(gt, "save_result_file", lambda user_id, job_uuid, ext, data: saved.setdefault("bytes", data))
    monkeypatch.setattr(gt, "job_heartbeat", _fake_hb)


def test_generated_image_carries_the_notice(monkeypatch):
    saved: dict = {}
    _base_mocks(monkeypatch, saved)
    response = _StubResponse(200, data={"data": [{"b64_json": base64.b64encode(_png_bytes()).decode()}]})
    monkeypatch.setattr(gt, "_image_http_client", lambda *a, **k: ("http://x", "some-model", _StubImageClient(response)))

    gt.run_image_generate.run.__func__(None, "job1", "a cat", "1024x1024", None)

    with Image.open(io.BytesIO(saved["bytes"])) as img:
        assert img.info.get("Comment") == AI_HINWEIS_TEXT


def test_edited_image_carries_the_notice(monkeypatch):
    saved: dict = {}
    _base_mocks(monkeypatch, saved)
    monkeypatch.setattr(gt, "get_file", lambda p: b"original-image-bytes")
    response = _StubResponse(200, headers={"content-type": "image/png"}, content=_png_bytes())
    monkeypatch.setattr(gt, "_image_http_client", lambda *a, **k: ("http://x", "some-model", _StubImageClient(response)))

    gt.run_image_edit.run.__func__(None, "job1", "ip", "cat.png", "make it blue", None)

    with Image.open(io.BytesIO(saved["bytes"])) as img:
        assert img.info.get("Comment") == AI_HINWEIS_TEXT
