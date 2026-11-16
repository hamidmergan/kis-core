"""The helpers several route files share: the own job, the account id, the upload size."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.routes import _shared
from src.routes.admin import feedback as admin_feedback

UUID = "a" * 32


def _jobs(monkeypatch, job):
    monkeypatch.setattr(_shared.db, "get_job", lambda job_uuid: job)


def test_own_job_returns_the_callers_job(monkeypatch):
    job = {"user_id": 7, "tool": "podcast"}
    _jobs(monkeypatch, job)
    assert _shared.own_job(UUID, {"user_id": 7}, "de", tool="podcast") is job


@pytest.mark.parametrize("job", [None, {"user_id": 8, "tool": "podcast"}, {"user_id": 7, "tool": "tts"}])
def test_missing_foreign_and_wrong_tool_answer_alike(monkeypatch, job):
    _jobs(monkeypatch, job)
    with pytest.raises(HTTPException) as fehler:
        _shared.own_job(UUID, {"user_id": 7}, "de", tool="podcast")
    assert fehler.value.status_code == 404


def test_a_malformed_uuid_never_reaches_the_database(monkeypatch):
    monkeypatch.setattr(_shared.db, "get_job", lambda job_uuid: pytest.fail("must not be asked"))
    with pytest.raises(HTTPException) as fehler:
        _shared.own_job("../x", {"user_id": 7}, "de")
    assert fehler.value.status_code == 400


def test_session_without_an_account_is_refused():
    assert _shared.require_user_id({"user_id": 3}, "de") == 3
    with pytest.raises(HTTPException) as fehler:
        _shared.require_user_id({}, "de")
    assert fehler.value.status_code == 401


def test_upload_size_follows_the_admin_limit(monkeypatch):
    monkeypatch.setattr(_shared.tool_limits, "max_upload_bytes", lambda: 10 * 1024 * 1024)
    anfrage = lambda laenge: SimpleNamespace(headers={"content-length": laenge} if laenge else {})  # noqa: E731
    _shared.enforce_upload_size(anfrage(None), "de")
    _shared.enforce_upload_size(anfrage(str(10 * 1024 * 1024)), "de")
    with pytest.raises(HTTPException) as fehler:
        _shared.enforce_upload_size(anfrage(str(10 * 1024 * 1024 + 1)), "de")
    assert fehler.value.status_code == 413
    assert "10" in fehler.value.detail


def test_feedback_attachment_from_s3_keeps_a_name_outside_latin1(monkeypatch):
    monkeypatch.setattr(admin_feedback.repo, "get_attachment", lambda attachment_id: {
        "filename": "Bildschirmfoto 講義.png", "content_type": "image/png", "storage_key": "k"})
    monkeypatch.setattr(admin_feedback, "USE_S3", True)
    monkeypatch.setattr(admin_feedback, "stream_s3_object", lambda key: (iter([b"x"]), 1, None))
    antwort = admin_feedback.get_feedback_attachment(1, admin={}, locale="de")
    kopf = antwort.headers["content-disposition"]
    assert kopf.startswith("inline; ")
    assert "filename*=UTF-8''" in kopf
