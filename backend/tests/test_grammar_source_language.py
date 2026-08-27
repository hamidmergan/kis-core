"""The grammar exercise follows the source language, not the course room's."""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training import _source_grammar as mod


@pytest.fixture
def gesendet(monkeypatch):
    """Captures what would go to the model, without calling it."""
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        inhalt = json.dumps({"title": "T", "exercises": []})
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=inhalt))])

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))

    def _lauf(language="German"):
        ctx = types.SimpleNamespace(context="Die Kammer fuehrt die Rolle.",
                                    source_hint="Quelle", multi_label="T",
                                    sections={}, source_by_name={})
        gtype = {"label": "Passiv Präsens", "rule": "Aktiv wird Passiv",
                 "example": {"before": "A", "after": "B"}}
        monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None, raising=False)
        mod.generate_grammar_from_source(client, "m", ctx, gtype, 3, language=language)
        return " ".join(m["content"] for msg in calls for m in msg)

    return _lauf


def test_the_sentences_follow_the_source_text(gesendet):
    text = gesendet()
    assert "SAME language as the source text" in text
    assert "Do NOT translate" in text


def test_no_target_language_is_imposed_on_the_sentences(gesendet):
    """The old sentence 'Write ALL sentences in {language}' must not come back."""
    text = gesendet()
    assert "Write ALL sentences in German" not in text
    assert "Write the output in German" not in text


def test_the_workspace_language_does_not_leak_into_the_prompt(gesendet):
    """Even with an English course room the instruction stays with the source."""
    text = gesendet(language="English")
    assert "Write ALL sentences in English" not in text
    assert "SAME language as the source text" in text


def test_the_instruction_line_still_follows_the_course(gesendet):
    """Instruction and labels are frame, not practice material."""
    assert mod.task_line("transform", "de", "Passiv Präsens") != \
        mod.task_line("transform", "en", "Passiv Präsens")
