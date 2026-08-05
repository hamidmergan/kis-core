"""Wer Grammatikthemen anlegen darf und wer sie nur wählen darf.

Anlegen ist Verwaltungsarbeit und hängt damit an Eigentum oder Tutor-Rolle. Wählen
darf jeder mit Zugang, sonst wäre die Liste für Studierende nutzlos. Der Systemrang
spielt wie überall im Workspace keine Rolle, weder zugunsten noch zulasten.

Zusätzlich geprüft: ein Thema aus einem fremden Kurs gilt als nicht vorhanden. Ohne
diese Prüfung könnte jemand mit Verwaltungsrechten in Kurs A ein Thema in Kurs B
löschen, indem er dessen id errät.
"""

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes import _helpers
from src.features.ai_assistant.routes.language_training import grammar_topics

EIGENTUEMER, TUTOR, LERNENDER, FREMDER = 1, 2, 3, 4
WORKSPACE = {"id": 7, "uuid": "w-1", "user_id": EIGENTUEMER}


@pytest.fixture
def workspace(monkeypatch):
    monkeypatch.setattr(_helpers.db, "get_aia_workspace", lambda uuid: WORKSPACE)
    monkeypatch.setattr(_helpers.db, "is_workspace_tutor", lambda ws, uid: uid == TUTOR)
    # Ein Tutor ist ueber eine Einschreibung im Kurs, deshalb zaehlt er hier mit.
    # is_student_enrolled fragt nur, ob es eine Einschreibung gibt, nicht welche Rolle
    # sie traegt.
    monkeypatch.setattr(_helpers.db, "is_student_enrolled",
                        lambda ws, uid: uid in (LERNENDER, TUTOR))


@pytest.mark.parametrize("user_id", [EIGENTUEMER, TUTOR])
def test_owner_and_tutor_may_create_topics(workspace, user_id):
    assert _helpers._require_workspace_manage("w-1", user_id)["id"] == 7


@pytest.mark.parametrize("user_id", [LERNENDER, FREMDER])
def test_nobody_else_may_create_topics(workspace, user_id):
    with pytest.raises(HTTPException) as err:
        _helpers._require_workspace_manage("w-1", user_id)
    assert err.value.status_code == 403


@pytest.mark.parametrize("user_id", [EIGENTUEMER, TUTOR, LERNENDER])
def test_everyone_with_access_may_read_the_list(workspace, user_id):
    assert _helpers._require_workspace_access("w-1", user_id)["id"] == 7


def test_a_stranger_cannot_even_read_the_list(workspace):
    with pytest.raises(HTTPException) as err:
        _helpers._require_workspace_access("w-1", FREMDER)
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
