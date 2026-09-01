"""The /translate route accepts pasted text as an alternative to a file upload."""
import asyncio

import pytest
from fastapi import HTTPException


class _Request:
    headers: dict = {}


def _wire(monkeypatch, route):
    monkeypatch.setattr(route.db, "create_job", lambda *a, **k: None)
    monkeypatch.setattr(route.db, "set_job_input_path", lambda *a, **k: None)
    monkeypatch.setattr(route, "save_queue_file_from_path", lambda *a, **k: "users/1/jobs/x/input")
    monkeypatch.setattr(route, "enforce_tool_burst", lambda *a, **k: None)
    monkeypatch.setattr(route, "enforce_quota", lambda *a, **k: None)
    monkeypatch.setattr(route, "is_admin_user", lambda u: False)

    import src.tasks.general_tasks as gt
    captured = {}

    def fake_delay(job_uuid, input_path, filename, *rest):
        captured["filename"] = filename

    monkeypatch.setattr(gt, "run_translate", type("T", (), {"delay": staticmethod(fake_delay)})())
    return captured


def test_text_input_queues_job_as_txt(monkeypatch):
    from src.routes import translate as route
    captured = _wire(monkeypatch, route)

    asyncio.run(route.translate(
        request=_Request(), file=None, text="Ein Satz zum Uebersetzen.",
        glossary="", provider_id=None, source_lang="", target_lang="",
        current_user={"user_id": 1}, locale="de",
    ))

    assert captured["filename"] == "text.txt"


def test_both_file_and_text_is_rejected(monkeypatch):
    from src.routes import translate as route
    _wire(monkeypatch, route)

    class _Upload:
        filename = "doc.txt"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(route.translate(
            request=_Request(), file=_Upload(), text="Text",
            glossary="", provider_id=None, source_lang="", target_lang="",
            current_user={"user_id": 1}, locale="de",
        ))
    assert exc.value.status_code == 400


def test_neither_file_nor_text_is_rejected(monkeypatch):
    from src.routes import translate as route
    _wire(monkeypatch, route)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(route.translate(
            request=_Request(), file=None, text="",
            glossary="", provider_id=None, source_lang="", target_lang="",
            current_user={"user_id": 1}, locale="de",
        ))
    assert exc.value.status_code == 400


def test_text_over_limit_is_rejected(monkeypatch):
    from src.routes import translate as route
    _wire(monkeypatch, route)
    monkeypatch.setattr(route, "TRANSLATE_MAX_CHARS", 10)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(route.translate(
            request=_Request(), file=None, text="x" * 20,
            glossary="", provider_id=None, source_lang="", target_lang="",
            current_user={"user_id": 1}, locale="de",
        ))
    assert exc.value.status_code == 422
