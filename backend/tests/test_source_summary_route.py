"""The summary of one source, fetched only when somebody opens it."""

import pytest
from fastapi.testclient import TestClient

from fastapi import FastAPI

from src.dependencies import get_current_user
from src.features.ai_assistant.routes.sources import router as sources_router

# The module router hangs on a feature switch, the route under test does not.
app = FastAPI()
app.include_router(sources_router, prefix="/api")

WORKSPACE = {"id": 5, "uuid": "ws-1", "user_id": 1, "is_active": True}
SOURCE = {"id": 7, "uuid": "src-1", "workspace_id": 5, "filename": "a.pdf",
          "summary": "Worum es geht."}


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "is_admin": False}
    monkeypatch.setattr("src.database.get_aia_workspace",
                        lambda uuid: WORKSPACE if uuid == "ws-1" else None)
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda uuid: SOURCE if uuid == "src-1" else None)
    monkeypatch.setattr("src.database.is_student_enrolled", lambda wid, uid: False)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _hole(client, ws="ws-1", src="src-1"):
    return client.get(f"/api/ai-assistant/workspaces/{ws}/sources/{src}/summary")


def test_the_owner_gets_the_summary(client):
    antwort = _hole(client)
    assert antwort.status_code == 200
    assert antwort.json()["summary"] == "Worum es geht."


def test_an_enrolled_student_gets_it_too(client, monkeypatch):
    # Everybody in the module may read what a material is about.
    monkeypatch.setattr("src.database.get_aia_workspace",
                        lambda uuid: {**WORKSPACE, "user_id": 99})
    monkeypatch.setattr("src.database.is_student_enrolled", lambda wid, uid: True)
    assert _hole(client).status_code == 200


def test_somebody_from_outside_gets_nothing(client, monkeypatch):
    monkeypatch.setattr("src.database.get_aia_workspace",
                        lambda uuid: {**WORKSPACE, "user_id": 99})
    monkeypatch.setattr("src.database.is_student_enrolled", lambda wid, uid: False)
    assert _hole(client).status_code == 403


def test_a_source_from_another_module_is_not_found(client, monkeypatch):
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda uuid: {**SOURCE, "workspace_id": 99})
    assert _hole(client).status_code == 404


def test_a_source_without_a_summary_answers_empty(client, monkeypatch):
    monkeypatch.setattr("src.database.get_aia_source", lambda uuid: {**SOURCE, "summary": None})
    assert _hole(client).json()["summary"] == ""


@pytest.fixture
def dispatch(monkeypatch):
    """Records progress writes and dispatched jobs instead of touching database and broker."""
    calls = {"progress": [], "cleared": [], "delay": []}
    monkeypatch.setattr("src.database.update_aia_source_progress",
                        lambda uuid, stage: calls["progress"].append((uuid, stage)))
    monkeypatch.setattr("src.database.clear_aia_source_progress",
                        lambda uuid: calls["cleared"].append(uuid))
    monkeypatch.setattr("src.database.is_workspace_tutor", lambda wid, uid: False)
    from src.features.ai_assistant.tasks.ingestion import run_summarize_source
    monkeypatch.setattr(run_summarize_source, "delay", lambda uuid: calls["delay"].append(uuid))
    return calls


def _hole_nach(client, ws="ws-1", src="src-1"):
    return client.post(f"/api/ai-assistant/workspaces/{ws}/sources/{src}/summary")


def test_a_missing_summary_is_caught_up(client, monkeypatch, dispatch):
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda uuid: {**SOURCE, "status": "ready", "summary": None})
    antwort = _hole_nach(client)
    assert antwort.status_code == 200
    assert dispatch["progress"] == [("src-1", "summarizing")]
    assert dispatch["delay"] == ["src-1"]


@pytest.mark.parametrize("zustand", [
    {"status": "ready"},
    {"status": "ready", "summary": None, "progress": {"stage": "summarizing"}},
    {"status": "indexing", "summary": None},
])
def test_no_catch_up_with_a_summary_or_while_busy(client, monkeypatch, dispatch, zustand):
    monkeypatch.setattr("src.database.get_aia_source", lambda uuid: {**SOURCE, **zustand})
    assert _hole_nach(client).status_code == 409
    assert dispatch["delay"] == []


def test_only_the_owner_may_catch_up(client, monkeypatch, dispatch):
    monkeypatch.setattr("src.database.get_aia_workspace",
                        lambda uuid: {**WORKSPACE, "user_id": 99})
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda uuid: {**SOURCE, "status": "ready", "summary": None})
    assert _hole_nach(client).status_code == 403
    assert dispatch["delay"] == []


def test_a_failed_dispatch_leaves_no_spinner(client, monkeypatch, dispatch):
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda uuid: {**SOURCE, "status": "ready", "summary": None})
    from src.features.ai_assistant.tasks.ingestion import run_summarize_source

    def kaputt(uuid):
        raise ConnectionError("broker down")
    monkeypatch.setattr(run_summarize_source, "delay", kaputt)
    with pytest.raises(ConnectionError):
        _hole_nach(client)
    assert dispatch["cleared"] == ["src-1"]
