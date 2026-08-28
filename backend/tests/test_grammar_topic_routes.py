"""Creating hangs off ownership or tutor, choosing is open to anyone with access."""

import types

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes import _workspace_access
from src.features.ai_assistant.routes.language_training import grammar_topics

EIGENTUEMER, TUTOR, LERNENDER, FREMDER = 1, 2, 3, 4
WORKSPACE = {"id": 7, "uuid": "w-1", "user_id": EIGENTUEMER}


@pytest.fixture
def workspace(monkeypatch):
    monkeypatch.setattr(_workspace_access.db, "get_aia_workspace", lambda uuid: WORKSPACE)
    monkeypatch.setattr(_workspace_access.db, "is_workspace_tutor", lambda ws, uid: uid == TUTOR)
    # A tutor is in the course through an enrollment and counts here.
    monkeypatch.setattr(_workspace_access.db, "is_student_enrolled",
                        lambda ws, uid: uid in (LERNENDER, TUTOR))


@pytest.mark.parametrize("user_id", [EIGENTUEMER, TUTOR])
def test_owner_and_tutor_may_create_topics(workspace, user_id):
    assert _workspace_access._require_workspace_manage("w-1", user_id)["id"] == 7


@pytest.mark.parametrize("user_id", [LERNENDER, FREMDER])
def test_nobody_else_may_create_topics(workspace, user_id):
    with pytest.raises(HTTPException) as err:
        _workspace_access._require_workspace_manage("w-1", user_id)
    assert err.value.status_code == 403


@pytest.mark.parametrize("user_id", [EIGENTUEMER, TUTOR, LERNENDER])
def test_everyone_with_access_may_read_the_list(workspace, user_id):
    assert _workspace_access._require_workspace_access("w-1", user_id)["id"] == 7


def test_a_stranger_cannot_even_read_the_list(workspace):
    with pytest.raises(HTTPException) as err:
        _workspace_access._require_workspace_access("w-1", FREMDER)
    assert err.value.status_code == 403


# ─── Themen fremder Kurse ────────────────────────────────────────────────────

def test_a_topic_from_another_workspace_counts_as_missing(monkeypatch):
    monkeypatch.setattr(grammar_topics.db, "get_grammar_topic",
                        lambda tid: {"id": tid, "workspace_id": 99, "name": "X"})
    with pytest.raises(HTTPException) as err:
        grammar_topics._topic_in_workspace(5, WORKSPACE, "de")
    assert err.value.status_code == 404


def test_a_topic_of_this_workspace_is_returned(monkeypatch):
    monkeypatch.setattr(grammar_topics.db, "get_grammar_topic",
                        lambda tid: {"id": tid, "workspace_id": 7, "name": "Konjunktiv II"})
    assert grammar_topics._topic_in_workspace(5, WORKSPACE, "de")["name"] == "Konjunktiv II"


def test_an_unknown_topic_is_missing(monkeypatch):
    monkeypatch.setattr(grammar_topics.db, "get_grammar_topic", lambda tid: None)
    with pytest.raises(HTTPException) as err:
        grammar_topics._topic_in_workspace(5, WORKSPACE, "de")
    assert err.value.status_code == 404


# ─── The name suggestion ─────────────────────────────────────────────────────

def _vorschau_ohne_modell(monkeypatch, derived):
    """The preview without a provider: only the route, not the model."""
    monkeypatch.setattr(grammar_topics, "_get_llm_client", lambda: ("c", "m", None))
    monkeypatch.setattr(grammar_topics.db, "get_aia_workspace", lambda uuid: WORKSPACE)
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks._helpers.tool_output_language",
        lambda ws_id: ("de", "German"))
    monkeypatch.setattr(grammar_topics, "derive_topic", lambda *a, **k: derived)


async def test_the_preview_hands_the_suggested_name_to_the_form(workspace, monkeypatch):
    """The form reads exactly this field."""
    _vorschau_ohne_modell(monkeypatch, {
        "rule": "r", "task_lines": {}, "label": "Passiv Präsens",
        "examples": [{"before": "Das Team schreibt.", "after": "Es wird geschrieben."}]})

    out = await grammar_topics.preview_topic(
        "w-1", types.SimpleNamespace(name="passi"), {"user_id": EIGENTUEMER}, "de")

    assert out["suggested_name"] == "Passiv Präsens"
    # The typed name stays untouched, nothing is overwritten.
    assert out["name"] == "passi"


async def test_a_missing_suggested_name_is_an_empty_field_and_not_an_error(
        workspace, monkeypatch):
    _vorschau_ohne_modell(monkeypatch, {
        "rule": "r", "task_lines": {},
        "examples": [{"before": "Das Team schreibt.", "after": "Es wird geschrieben."}]})

    out = await grammar_topics.preview_topic(
        "w-1", types.SimpleNamespace(name="Perfekt"), {"user_id": EIGENTUEMER}, "de")

    assert out["suggested_name"] == ""
