"""A summary that derails is thrown away and asked again."""

import types

import pytest

from src.services import aia_summarizer as sm


SAUBER = "Der Terminplan nennt die Belegung vom 01.09. bis 27.09.2026."


@pytest.mark.parametrize("text", [
    "Evaluation der Lehrveranstaltungen vom //////////////////// 1.12.",
    "Anmeldung via QIS vom 04.01. bis 13.01._ _ _ _ _ _ _ _ _ _ _ __",
    "Belegung vom 01.09. - - - - - - - - - - - - - - - - bis 27.09.",
])
def test_a_run_of_the_same_character_is_derailed(text):
    assert sm._is_derailed(text) is True


@pytest.mark.parametrize("text", [
    "... (Wait, let me rephrase for conciseness)",
    "Prüfungen WS: Anmeldung (Wait, let me restart the list for clarity).",
])
def test_the_model_talking_to_itself_is_derailed(text):
    assert sm._is_derailed(text) is True


@pytest.mark.parametrize("text", [
    SAUBER,
    "Kapitel 3 -- Grundlagen, siehe S. 12 ff.",
    "Die Formel lautet a == b und c != d.",
])
def test_ordinary_text_is_not_derailed(text):
    assert sm._is_derailed(text) is False


def test_an_empty_answer_is_not_called_derailed():
    assert sm._is_derailed("") is False


# --- the retry --------------------------------------------------------------

def _client(antworten: list[str], calls: list):
    def create(**kw):
        calls.append(kw)
        msg = types.SimpleNamespace(content=antworten[len(calls) - 1])
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg,
                                                                   finish_reason="stop")])
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def test_a_derailed_answer_is_asked_again(monkeypatch):
    monkeypatch.setattr(sm.time, "sleep", lambda s: None)
    calls = []
    text = sm._call(_client(["////////////////", SAUBER], calls), "m", "sys", "user", retries=2)
    assert text == SAUBER
    assert len(calls) == 2


def test_a_derailed_answer_to_the_last_attempt_still_comes_back(monkeypatch):
    # Half a summary is better than none, the source itself is long done.
    monkeypatch.setattr(sm.time, "sleep", lambda s: None)
    calls = []
    text = sm._call(_client(["////////////////", "////////////////"], calls), "m",
                    "sys", "user", retries=1)
    assert text.startswith("////")
    assert len(calls) == 2


# --- prevention -------------------------------------------------------------

def test_the_request_switches_thinking_off():
    # A thinking model leaked its own musings into the summary.
    from src.features.ai_assistant.prompts import summarizer_prompts as sp
    assert sp.aia_summary_user("Inhalt").startswith("/no_think")
    assert sp.aia_summary_combine_user(["a", "b"]).startswith("/no_think")


def test_the_rules_forbid_thinking_out_loud():
    from src.features.ai_assistant.prompts import summarizer_prompts as sp
    for regeln in (sp.aia_summary_system(), sp.aia_summary_combine_system()):
        assert "never comment on your own" in regeln.lower()


def test_the_call_goes_out_without_a_frequency_penalty():
    # Measured: the penalty punishes the words a schedule has to repeat, and the
    # model swerves into rows of slashes instead.
    calls = []
    sm._call(_client([SAUBER], calls), "m", "sys", "user", retries=0)
    assert "frequency_penalty" not in calls[0]
