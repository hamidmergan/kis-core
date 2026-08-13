"""Die gewaehlte Formatauswahl steuert Plan und Prompt.

Gemischt bleibt, was es war: alle vier reihum. Eine eigene Auswahl verteilt reihum
ueber genau die gewaehlten Arten, und im Prompt steht kein Wort ueber die anderen.

Kein DB- und kein Netzzugriff.
"""

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


# --- Der Plan -----------------------------------------------------------------

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
    """Bestehende Regel: geht es nicht glatt auf, bekommen die vorderen einen mehr."""
    plan = item_plan(7, ["transform", "cloze", "statement"])
    assert plan.count("transform") == 3
    assert plan.count("cloze") == 2
    assert plan.count("statement") == 2


def test_an_empty_choice_falls_back_to_all_four():
    """Die Route laesst das nicht durch, aber der Plan darf daran nicht zerbrechen."""
    assert item_plan(4, []) == list(KINDS)


# --- Der Prompt ---------------------------------------------------------------

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


# --- Der Nachschlag -----------------------------------------------------------

_ONLY_STATEMENT = {
    "kind": "statement",
    "statement": "Die Messwerte werden vom Server gespeichert.",
    "answer": True,
}


@pytest.fixture
def no_db_attachment(monkeypatch):
    """Mock attach_chips_cited damit der Test ohne Datenbankzugriff laeuft."""
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks.language_training._source_grammar"
        ".attach_chips_cited", lambda items, claims, ctx, **kw: None)


def test_an_unchosen_kind_is_always_rejected_even_on_the_last_draw(no_db_attachment):
    """Ein abgehaktes Kaestchen ist ein Ausschluss, keine Vorliebe. Auch im letzten Wurf
    wird ein Format, das nicht in der Auswahl steht, verworfen. Ohne diese Sperre kaeme
    eine Richtig/Falsch-Aufgabe heraus, obwohl der Lernende nur "Umformen" ausgewaehlt hat."""
    antwort = json.dumps({"title": "T", "exercises": [_ONLY_STATEMENT]})
    client, _ = _client_queue(antwort)

    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 2,
        locale="de", kinds=["transform"])

    # Es wurde eine Richtig/Falsch-Aufgabe angeboten, aber sie haette nicht akzeptiert
    # werden duerfen: die Art steht nicht in der Auswahl.
    assert items == []


def test_an_unchosen_kind_is_accepted_when_gemischt(no_db_attachment):
    """Ohne Auswahl (Gemischt) werden alle vier Arten akzeptiert, auch im letzten Wurf."""
    antwort = json.dumps({"title": "T", "exercises": [_ONLY_STATEMENT]})
    client, _ = _client_queue(antwort)

    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 1,
        locale="de", kinds=None)

    # Ohne Auswahl ist Richtig/Falsch erlaubt.
    assert len(items) == 1
    assert "Ist der Satz korrekt?" in items[0]["front"]


def _client_queue(*contents):
    """Fake-Client, der die Antworten der Reihe nach ausgibt. Die letzte wiederholt
    sich, damit ein Test nicht an der Anzahl der Würfe hängt."""
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
