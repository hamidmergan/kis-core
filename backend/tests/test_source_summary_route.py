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
