"""The 'recording too long' refusal has to arrive in the user's language."""
import pytest

from src.limits import MAX_AUDIO_SEC
from src.services.openai_compat_llm._chunking import AudioTooLongError
from src.tasks import _errors


@pytest.fixture
def captured(monkeypatch):
    """Record what handle_task_exception writes, and set the job's locale."""
    written: dict = {}
    locale_holder = {"locale": "de"}

    monkeypatch.setattr(_errors.db, "get_job", lambda j: {"creator_locale": locale_holder["locale"]})
    monkeypatch.setattr(
        _errors.db, "update_job_status",
        lambda job_uuid, status, error_message=None: written.update(
            {"status": status, "msg": error_message}
        ),
    )
    return written, locale_holder


def test_german_job_gets_german_wording(captured):
    written, locale_holder = captured
    locale_holder["locale"] = "de"

    _errors.handle_task_exception("j1", AudioTooLongError(11004.0, MAX_AUDIO_SEC), task_label="Transcribe")

    assert written["status"] == "failed"
    assert "zu lang" in written["msg"]
    assert "183" in written["msg"]        # 11004 s = 183.4 min
    assert "100" in written["msg"]        # the limit, in minutes


def test_english_job_gets_english_wording(captured):
    written, locale_holder = captured
    locale_holder["locale"] = "en"

    _errors.handle_task_exception("j2", AudioTooLongError(11004.0, MAX_AUDIO_SEC), task_label="Transcribe")

    assert written["status"] == "failed"
    assert "too long" in written["msg"].lower()
    assert "zu lang" not in written["msg"]
    assert "183" in written["msg"]


def test_other_errors_still_pass_through_verbatim(captured):
    written, _ = captured

    _errors.handle_task_exception("j3", RuntimeError("ffprobe exploded"), task_label="Transcribe")

    assert written["msg"] == "ffprobe exploded"


def test_limit_is_reported_in_minutes_from_the_real_constant(captured):
    """Raising the ceiling must change the message, not just the check."""
    written, _ = captured

    _errors.handle_task_exception("j4", AudioTooLongError(MAX_AUDIO_SEC + 60, MAX_AUDIO_SEC), task_label="Transcribe")

    assert str(MAX_AUDIO_SEC // 60) in written["msg"]
