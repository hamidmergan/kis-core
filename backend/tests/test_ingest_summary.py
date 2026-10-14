"""The per-source summary at ingest: it runs, and without it the source is not finished."""

import pytest

from src.features.ai_assistant.tasks import ingestion


CHUNKS = [{"content": "Ein Satz über Projektmanagement."}]


@pytest.fixture
def welt(monkeypatch):
    """Database and model under test control."""
    state = {"gespeichert": None, "fortschritt": [], "status": []}
    monkeypatch.setattr("src.database.update_aia_source_status",
                        lambda uuid, status, **k: state["status"].append((status, k)))
    monkeypatch.setattr("src.database.get_aia_sources_by_workspace", lambda wid: [])
    monkeypatch.setattr("src.database.update_aia_source_summary",
                        lambda uuid, text: state.__setitem__("gespeichert", text))
    monkeypatch.setattr("src.database.update_aia_source_progress",
                        lambda uuid, schritt: state["fortschritt"].append(schritt))
    monkeypatch.setattr("src.database.clear_aia_source_progress",
                        lambda uuid: state["fortschritt"].append("clear"))
    monkeypatch.setattr("src.database.get_setting", lambda key, default: default)
    monkeypatch.setattr("src.features.ai_assistant.tasks._helpers._get_llm_client",
                        lambda: ("client", "modell", None))
    return state


def test_the_switch_is_on():
    # The overview tools read the summary now, so it has to be built.
    assert ingestion._BUILD_INGEST_SUMMARY is True


def test_the_summary_is_stored(welt, monkeypatch):
    monkeypatch.setattr("src.services.aia_summarizer.build_source_summary",
                        lambda chunks, client, model, cap: "Kurzfassung")
    ingestion._build_source_summary_safely("u1", CHUNKS)
    assert welt["gespeichert"] == "Kurzfassung"


def test_a_failing_summary_reports_false(welt, monkeypatch):
    def kaputt(*a, **k):
        raise RuntimeError("Anbieter weg")

    monkeypatch.setattr("src.services.aia_summarizer.build_source_summary", kaputt)
    assert ingestion._build_source_summary_safely("u1", CHUNKS) is False
    assert welt["gespeichert"] is None


def test_a_source_without_chunks_asks_no_model(welt, monkeypatch):
    monkeypatch.setattr("src.services.aia_summarizer.build_source_summary",
                        lambda *a, **k: pytest.fail("no model call for an empty source"))
    assert ingestion._build_source_summary_safely("u1", []) is True
    assert welt["gespeichert"] is None


# --- backfill task ----------------------------------------------------------

def test_the_backfill_task_summarises_one_source(welt, monkeypatch):
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda uuid: {"id": 7, "uuid": uuid, "workspace_id": 5})
    monkeypatch.setattr("src.database.get_chunks_by_source", lambda sid: CHUNKS)
    monkeypatch.setattr("src.services.aia_summarizer.build_source_summary",
                        lambda chunks, client, model, cap: "Kurzfassung")
    ingestion.run_summarize_source("u1")
    assert welt["gespeichert"] == "Kurzfassung"
    assert welt["status"] == [("ready", {})]


def test_a_failed_resume_marks_the_source_failed_again(welt, monkeypatch):
    # The row must not keep spinning, it goes back to failed with the retry icon.
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda uuid: {"id": 7, "uuid": uuid, "workspace_id": 5})
    monkeypatch.setattr("src.database.get_chunks_by_source", lambda sid: CHUNKS)

    def kaputt(*a, **k):
        raise RuntimeError("Anbieter weg")

    monkeypatch.setattr("src.services.aia_summarizer.build_source_summary", kaputt)
    ingestion.run_summarize_source("u1", "en")
    status, felder = welt["status"][-1]
    assert status == "failed"
    assert felder["error_message"]


def test_the_backfill_task_skips_a_source_that_is_gone(welt, monkeypatch):
    monkeypatch.setattr("src.database.get_aia_source", lambda uuid: None)
    monkeypatch.setattr("src.services.aia_summarizer.build_source_summary",
                        lambda *a, **k: pytest.fail("no model call for a missing source"))
    ingestion.run_summarize_source("weg")
    assert welt["gespeichert"] is None


# --- the progress marker ----------------------------------------------------

def test_the_progress_marker_is_cleared_when_the_summary_is_done(welt, monkeypatch):
    monkeypatch.setattr("src.services.aia_summarizer.build_source_summary",
                        lambda chunks, client, model, cap: "Kurzfassung")
    ingestion._build_source_summary_safely("u1", CHUNKS)
    assert welt["fortschritt"] == ["summarizing", "clear"]


def test_a_failing_summary_leaves_no_spinner_behind(welt, monkeypatch):
    # A source stuck on "summarizing" spins in the interface for ever.
    def kaputt(*a, **k):
        raise RuntimeError("Anbieter weg")

    monkeypatch.setattr("src.services.aia_summarizer.build_source_summary", kaputt)
    ingestion._build_source_summary_safely("u1", CHUNKS)
    assert welt["fortschritt"][-1] == "clear"
