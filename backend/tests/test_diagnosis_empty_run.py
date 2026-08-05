"""The empty run: everything skipped means a fixed A1 with no model call.

Without this the grading call receives a record of twelve blank answers and has
to invent a level, which lands on A1 or A2 at random and comes with a made-up
strength in the closing message.
"""

import pytest

from src.services.aia_diagnosis_chat import is_empty_run


def _run(*answers) -> list[dict]:
    """Build a transcript of question/answer pairs.

    Each argument is either the typed text, or a ``(text, selected)`` tuple for a
    question where the learner clicked an option.
    """
    history: list[dict] = []
    for i, item in enumerate(answers, 1):
        text, selected = item if isinstance(item, tuple) else (item, None)
        history.append({"role": "assistant", "content": f"Frage {i}"})
        turn: dict = {"role": "user", "content": text}
        if selected is not None:
            turn["selected"] = selected
        history.append(turn)
    return history


def test_empty_run_when_nothing_was_given():
    assert is_empty_run(_run("", "", "")) is True


def test_empty_run_tolerates_whitespace_answers():
    """A learner who hits space before skipping still gave nothing."""
    assert is_empty_run(_run("", "   ", "\n")) is True


def test_empty_run_ignores_an_empty_selection_list():
    assert is_empty_run(_run(("", []), ("", []))) is True


def test_not_empty_when_any_text_was_typed():
    assert is_empty_run(_run("", "Ich gehe ins Kino.", "")) is False


def test_not_empty_when_an_option_was_clicked():
    """A tick without text is still an answer, so the model grades it."""
    assert is_empty_run(_run("", ("", ["gehe"]), "")) is False


def test_empty_history_is_not_an_empty_run():
    """No answered item at all is not an empty run, it is no run.

    Guards the ``all()`` on an empty sequence, which is True and would otherwise
    hand out A1 to a transcript that never started.
    """
    assert is_empty_run([]) is False


# ─── The endpoint ──────────────────────────────────────────────────────────

from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from src.services.aia_diagnosis_chat import resolve_question_plan  # noqa: E402

ROUTE = "src.features.ai_assistant.routes.language_training.diagnosis"


@pytest.fixture
def client(monkeypatch):
    # Without an LDAP server the app runs in local mode, where a middleware
    # mints a session from the database on every request. Setting the variable
    # keeps the request out of the DB, the same way the LDAP route tests do.
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")

    from src.app import app
    from src.dependencies import get_current_user, get_llm_client, get_settings
    from src.dependencies_rbac import require_aia_access
    from src.security.auth import verify_auth

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[require_aia_access] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    # A real client would need a provider; if the empty branch ever reaches for
    # one, the patched _call_llm below records it.
    app.dependency_overrides[get_llm_client] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _fake_completion(content: str):
    """Shape the OpenAI client returns: ``.choices[0].message.content``."""
    message = type("Msg", (), {"content": content})()
    choice = type("Choice", (), {"message": message})()
    return type("Completion", (), {"choices": [choice]})()


def _full_skip_history() -> list[dict]:
    """A finished German run in which every single question was skipped."""
    total = len(resolve_question_plan("", "de"))
    return _run(*[""] * total)


def test_all_skipped_gives_a_fixed_a1_without_asking_the_model(client):
    with patch(f"{ROUTE}._require_workspace_access",
               return_value={"id": 7, "diagnosis_language": "de"}), \
         patch(f"{ROUTE}.db.is_language_training_active", return_value=True), \
         patch(f"{ROUTE}.db.get_setting", side_effect=lambda key, default="": default), \
         patch(f"{ROUTE}.db.set_user_language_level") as save, \
         patch(f"{ROUTE}._call_llm") as call_llm:
        response = client.post(
            "/ai-assistant/language-diagnosis/turn",
            json={"workspace_uuid": "ws-1", "history": _full_skip_history()},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["done"] is True
    assert body["level"] == "A1"
    assert body["message"].strip()
    call_llm.assert_not_called()
    save.assert_called_once_with(1, "A1")


def test_a_single_answer_still_goes_to_the_model(client):
    """One typed sentence anywhere and the normal grading call runs.

    There is no middle ground: the fixed A1 applies only to a run with nothing
    in it at all.
    """
    history = _full_skip_history()
    history[1]["content"] = "Ich gehe ins Kino."

    with patch(f"{ROUTE}._require_workspace_access",
               return_value={"id": 7, "diagnosis_language": "de"}), \
         patch(f"{ROUTE}.db.is_language_training_active", return_value=True), \
         patch(f"{ROUTE}.db.get_setting", side_effect=lambda key, default="": default), \
         patch(f"{ROUTE}.db.set_user_language_level"), \
         patch(f"{ROUTE}.enforce_aia_burst"), \
         patch(f"{ROUTE}._call_llm") as call_llm:
        call_llm.return_value = _fake_completion(
            '{"done": true, "message": "Weiter so.", "level": "A2"}'
        )
        response = client.post(
            "/ai-assistant/language-diagnosis/turn",
            json={"workspace_uuid": "ws-1", "history": history},
        )

    assert response.status_code == 200
    assert response.json()["level"] == "A2"
    call_llm.assert_called_once()
