"""Retry of a source whose summary failed: it resumes there and keeps chunks and vectors."""

import pytest
from fastapi.testclient import TestClient

from fastapi import FastAPI

from src.dependencies import get_current_user
from src.features.ai_assistant.routes.sources import router as sources_router
from src.features.ai_assistant.tasks import ingestion

app = FastAPI()
app.include_router(sources_router, prefix="/api")

WORKSPACE = {"id": 5, "uuid": "ws-1", "user_id": 1, "is_active": True}
GESCHEITERT = {"id": 7, "uuid": "src-1", "workspace_id": 5, "filename": "a.pdf",
               "file_type": "pdf", "status": "failed", "summary": None, "ocr_info": None}


@pytest.fixture
def welt(monkeypatch):
    state = {"quelle": dict(GESCHEITERT), "chunks": (12, 0), "aufrufe": []}
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "is_admin": False}
    monkeypatch.setattr("src.database.get_aia_workspace",
                        lambda uuid: WORKSPACE if uuid == "ws-1" else None)
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda uuid: state["quelle"] if uuid == "src-1" else None)
    monkeypatch.setattr("src.database.is_workspace_tutor", lambda wid, uid: False)
    monkeypatch.setattr("src.database.count_chunks_and_unembedded", lambda sid: state["chunks"])
    monkeypatch.setattr("src.database.resume_aia_source_summary",
                        lambda uuid: state["aufrufe"].append("weiter"))
    monkeypatch.setattr("src.database.delete_aia_chunks_by_source",
                        lambda sid: state["aufrufe"].append("chunks weg"))
    monkeypatch.setattr("src.database.reset_aia_source_for_retry",
                        lambda uuid: state["aufrufe"].append("neu"))
    monkeypatch.setattr(ingestion.run_summarize_source, "delay",
                        lambda uuid, locale: state["aufrufe"].append("zusammenfassen"))
    monkeypatch.setattr("src.features.ai_assistant.routes.sources._upload._enqueue_index_source",
                        lambda uuid, uid, locale: state["aufrufe"].append("indexieren"))
    state["client"] = TestClient(app)
    yield state
    app.dependency_overrides.clear()


def _retry(client):
    return client.post("/api/ai-assistant/workspaces/ws-1/sources/src-1/retry")


def test_a_missing_summary_resumes_at_the_summary(welt):
    antwort = _retry(welt["client"])
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "indexing"
    assert welt["aufrufe"] == ["weiter", "zusammenfassen"]


def test_unembedded_chunks_start_from_scratch(welt):
    welt["chunks"] = (12, 3)
    antwort = _retry(welt["client"])
    assert antwort.json()["status"] == "pending"
    assert welt["aufrufe"] == ["chunks weg", "neu", "indexieren"]


def test_a_source_without_chunks_starts_from_scratch(welt):
    welt["chunks"] = (0, 0)
    assert _retry(welt["client"]).json()["status"] == "pending"
    assert "zusammenfassen" not in welt["aufrufe"]


def test_a_source_with_summary_starts_from_scratch(welt):
    # A summary is there, so the failure lies elsewhere.
    welt["quelle"] = {**GESCHEITERT, "summary": "Worum es geht."}
    assert _retry(welt["client"]).json()["status"] == "pending"
    assert "zusammenfassen" not in welt["aufrufe"]
