"""The coverage rule reaches the system prompt of every generator.

What the rule SAYS, how the context is split into equal numbered sections and how the
result is checked afterwards live in test_exercise_sections. This file only proves the
wiring: a rule that never reaches the prompt cannot spread anything.
"""

import json
import types

from src.features.ai_assistant.tasks.language_training._context import (
    QuelleContext,
    coverage_rule,
)

MARKER = "\n\nCOVERAGE. The source material is split into 2 numbered sections."


def _ctx(*labels):
    return QuelleContext(
        context="ctx", first_label=labels[0] if labels else "",
        multi_label="T", source_hint="Quelle",
        source_by_name={label: {"id": i} for i, label in enumerate(labels)},
        sections={i: label for i, label in enumerate(labels, start=1)},
    )


def _make_client(content):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _system_of(calls):
    return calls[0][0]["content"]


def test_flashcards_prompt_carries_the_rule(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_flashcards as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps(
        {"title": "T", "cards": [{"begriff": "X", "definition": "Y"}]}))
    mod.generate_flashcards_from_source(client, "m", _ctx("a.pdf", "b.pdf"), 1,
                                        locale="de", coverage=MARKER)
    assert MARKER in _system_of(calls)


def test_karteikarten_prompt_carries_the_rule(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_cards as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps(
        {"title": "T", "cards": [{"question": "Q", "answer": "A"}]}))
    mod.generate_cards_from_source(client, "m", _ctx("a.pdf", "b.pdf"), 1,
                                   locale="de", coverage=MARKER)
    assert MARKER in _system_of(calls)


def test_quiz_prompt_carries_the_rule(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]}))
    mod.generate_mc_from_source(client, "m", _ctx("a.pdf", "b.pdf"), 1,
                                locale="de", coverage=MARKER)
    assert MARKER in _system_of(calls)


def test_grammar_prompt_carries_the_rule(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_grammar as mod
    from src.services.aia_grammar_types import GRAMMAR_TYPES
    monkeypatch.setattr(mod, "attach_chips_cited", lambda *a, **k: None)
    client, calls = _make_client(json.dumps({
        "title": "T",
        "example": {"before": "Der Server speichert die Werte.",
                    "after": "Die Werte werden vom Server gespeichert."},
        "exercises": [
            {"before": "Die Software prüft die Eingaben.",
             "after": "Die Eingaben werden von der Software geprüft."},
            {"before": "Der Server speichert die Messwerte.",
             "after": "Die Messwerte werden vom Server gespeichert."},
        ],
    }))
    mod.generate_grammar_from_source(client, "m", _ctx("a.pdf", "b.pdf"),
                                     GRAMMAR_TYPES[0], 2, locale="de", coverage=MARKER)
    assert MARKER in _system_of(calls)


def test_one_source_leaves_the_prompt_untouched(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]}))
    ctx = _ctx("nur_eine.pdf")
    mod.generate_mc_from_source(client, "m", ctx, 1, locale="de",
                                coverage=coverage_rule(ctx, 1))
    assert "COVERAGE" not in _system_of(calls)


def test_every_generator_keeps_the_models_section_claim(monkeypatch):
    """The claim is what makes coverage checkable. It must survive item building, and it
    must not reach the database: finalize_exercise_set only reads known keys."""
    from src.features.ai_assistant.tasks.language_training import _source_mc as mc
    from src.features.ai_assistant.tasks.language_training import _source_cards as cards
    from src.features.ai_assistant.tasks.language_training import _source_flashcards as fc
    from src.features.ai_assistant.tasks.language_training import _source_grammar as gr
    from src.services.aia_grammar_types import GRAMMAR_TYPES
    for mod in (mc, cards, fc):
        monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    # Die Grammatik-Übung nimmt den gestaffelten Weg (Modell-Seite vor Rücksuche).
    monkeypatch.setattr(gr, "attach_chips_cited", lambda *a, **k: None)

    client, _ = _make_client(json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b"], "correct_idx": 0, "section": 2}]}))
    items, _ = mc.generate_mc_from_source(client, "m", _ctx("a.pdf", "b.pdf"), 1, locale="de")
    assert items[0]["_section"] == 2

    client, _ = _make_client(json.dumps(
        {"title": "T", "cards": [{"question": "Q", "answer": "A", "section": 2}]}))
    items, _ = cards.generate_cards_from_source(client, "m", _ctx("a.pdf", "b.pdf"), 1, locale="de")
    assert items[0]["_section"] == 2

    client, _ = _make_client(json.dumps(
        {"title": "T", "cards": [{"begriff": "X", "definition": "Y", "section": 2}]}))
    items, _ = fc.generate_flashcards_from_source(client, "m", _ctx("a.pdf", "b.pdf"), 1, locale="de")
    assert items[0]["_section"] == 2

    client, _ = _make_client(json.dumps({
        "title": "T",
        "example": {"before": "Der Server speichert die Werte.",
                    "after": "Die Werte werden vom Server gespeichert."},
        "exercises": [
            {"before": "Die Software prüft die Eingaben.",
             "after": "Die Eingaben werden von der Software geprüft.", "section": 2},
            {"before": "Der Server speichert die Messwerte.",
             "after": "Die Messwerte werden vom Server gespeichert.", "section": 1},
        ],
    }))
    items, _, _ = gr.generate_grammar_from_source(
        client, "m", _ctx("a.pdf", "b.pdf"), GRAMMAR_TYPES[0], 2, locale="de")
    assert [i["_section"] for i in items] == [2, 1]
