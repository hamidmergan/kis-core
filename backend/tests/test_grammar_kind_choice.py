"""The chosen format selection steers plan and prompt."""

import json
import types
import pytest

from src.features.ai_assistant.tasks.language_training._source_grammar import (
    KINDS,
    generate_grammar_from_source,
    item_plan,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


_TOPIC = {
    "id": 1,
    "label": "Passiv Präsens",
    "rule": "Input: an active sentence. Output: the same statement in the passive.",
    "example": {"before": "Hilde erklärt einen Begriff.",
                "after": "Ein Begriff wird von Hilde erklärt."},
    "examples": [{"before": "Hilde erklärt einen Begriff.",
                  "after": "Ein Begriff wird von Hilde erklärt."}],
}


def _ctx():
    return QuelleContext(
        context="[A.pdf, S. 4] Der Server speichert die Messwerte.",
        first_label="A.pdf", multi_label="A.pdf", source_hint="folgender Source",
        source_by_name={"A.pdf": {"id": 1, "workspace_id": 7}},
        seen_pages_by_source={1: {4}},
    )


def _client(content):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


# --- The plan -----------------------------------------------------------------

def test_without_a_choice_the_plan_is_all_four():
    assert item_plan(4) == list(KINDS)


def test_none_means_the_same_as_no_argument():
    assert item_plan(8, None) == item_plan(8)


def test_two_kinds_split_the_count_evenly():
    assert item_plan(6, ["transform", "cloze"]) == [
        "transform", "cloze", "transform", "cloze", "transform", "cloze"]


def test_one_kind_takes_everything():
    assert item_plan(3, ["choice"]) == ["choice", "choice", "choice"]


def test_an_uneven_count_gives_the_front_kinds_one_more():
    """Existing rule: when it does not divide evenly, the front ones get one more."""
    plan = item_plan(7, ["transform", "cloze", "statement"])
    assert plan.count("transform") == 3
    assert plan.count("cloze") == 2
    assert plan.count("statement") == 2


def test_an_empty_choice_falls_back_to_all_four():
    """The route does not let this through, but the plan must not break on it."""
    assert item_plan(4, []) == list(KINDS)


# --- The prompt ---------------------------------------------------------------

def test_the_prompt_only_names_the_chosen_kinds():
    client, calls = _client(json.dumps({"title": "T", "exercises": []}))
    generate_grammar_from_source(client, "m", _ctx(), _TOPIC, 4,
                                 locale="de", kinds=["transform"])

    prompt = calls[0][0]["content"]
    assert '4 of kind "transform"' in prompt
    assert 'of kind "cloze"' not in prompt
    assert 'of kind "statement"' not in prompt
    assert 'of kind "choice"' not in prompt


def test_without_a_choice_the_prompt_names_all_four():
    client, calls = _client(json.dumps({"title": "T", "exercises": []}))
    generate_grammar_from_source(client, "m", _ctx(), _TOPIC, 4, locale="de")

    prompt = calls[0][0]["content"]
    for kind in KINDS:
        assert f'of kind "{kind}"' in prompt


# --- The top-up ---------------------------------------------------------------

_ONLY_STATEMENT = {
    "kind": "statement",
    "statement": "Die Messwerte werden vom Server gespeichert.",
    "answer": True,
}


@pytest.fixture
def no_db_attachment(monkeypatch):
    """Mock attach_chips_cited so the test runs without database access."""
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks.language_training._source_grammar"
        ".attach_chips_cited", lambda items, claims, ctx, **kw: None)


def test_an_unchosen_kind_is_always_rejected_even_on_the_last_draw(no_db_attachment):
    """An unticked box is an exclusion, in the last attempt too."""
    antwort = json.dumps({"title": "T", "exercises": [_ONLY_STATEMENT]})
    client, _ = _client_queue(antwort)

    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 2,
        locale="de", kinds=["transform"])

    # The kind is not in the selection and must not be accepted.
    assert items == []


def test_an_unchosen_kind_is_accepted_when_gemischt(no_db_attachment):
    """Without a selection all four kinds are accepted, in the last attempt too."""
    antwort = json.dumps({"title": "T", "exercises": [_ONLY_STATEMENT]})
    client, _ = _client_queue(antwort)

    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 1,
        locale="de", kinds=None)

    # Without a selection true/false is allowed.
    assert len(items) == 1
    assert "Ist der Satz korrekt?" in items[0]["front"]


def _client_queue(*contents):
    """A stub client that returns the answers in order."""
    calls = []
    queue = list(contents)

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = queue.pop(0) if len(queue) > 1 else queue[0]
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls
