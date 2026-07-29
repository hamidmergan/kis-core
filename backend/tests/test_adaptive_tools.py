"""Tests for the adaptive language level of the generated study tools.

Two layers:
* the pure ``adaptive_tool_appendix`` builder and the DB-backed
  ``build_adaptive_tool_suffix`` (mirrors the chat's ``test_adaptive_chat``);
* the wiring proof that each tool builder actually appends the suffix to the
  system prompt it sends to the model (with a fake client, no DB, no network).
"""

import json
import types

from src.services.aia_adaptive_tools import (
    ADAPTIVE_TOOL_BEHAVIOR_SETTING,
    DEFAULT_ADAPTIVE_TOOL_BEHAVIOR,
    EXAMPLE_PLACEHOLDER,
    LEVEL_PLACEHOLDER,
    adaptive_tool_appendix,
    build_adaptive_tool_suffix,
)

# A distinctive suffix so a wiring test can prove it reached the system prompt.
MARKER = "\n\nADAPT-MARKER: pitch this at level A1."


def _make_client(content):
    """Minimal OpenAI-client stand-in: records the messages of every call and
    always returns ``content`` as the completion."""
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        choice = types.SimpleNamespace(message=message)
        return types.SimpleNamespace(choices=[choice])

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    return client, calls


def _system_of(calls):
    """The system-prompt content of the first recorded call."""
    return calls[0][0]["content"]


# --- the pure builder -------------------------------------------------------

def test_no_level_means_no_change():
    suffix, applied = adaptive_tool_appendix(None, DEFAULT_ADAPTIVE_TOOL_BEHAVIOR)
    assert suffix == ""
    assert applied is None


def test_empty_behavior_means_no_change():
    suffix, applied = adaptive_tool_appendix("A2", "   ")
    assert suffix == ""
    assert applied is None


def test_level_and_behavior_build_suffix():
    suffix, applied = adaptive_tool_appendix("A2", "Generate items for {level}.")
    assert applied == "A2"
    assert "A2" in suffix
    assert suffix.startswith("\n")


def test_appendix_substitutes_level_and_example():
    suffix, applied = adaptive_tool_appendix("A2", "Level {level}. Sample: {example}", "Hallo.")
    assert applied == "A2"
    assert "Level A2. Sample: Hallo." in suffix
    assert "{level}" not in suffix and "{example}" not in suffix


def test_default_behavior_carries_both_placeholders():
    assert LEVEL_PLACEHOLDER in DEFAULT_ADAPTIVE_TOOL_BEHAVIOR
    assert EXAMPLE_PLACEHOLDER in DEFAULT_ADAPTIVE_TOOL_BEHAVIOR


def test_default_behavior_overrides_covers_bands_and_guards_format():
    """The default must override the tool's own register rules, give a rule for
    every band, keep a consistent informal address, and -- unlike the chat
    version -- forbid changing the item count / JSON / correct answer."""
    b = DEFAULT_ADAPTIVE_TOOL_BEHAVIOR
    assert "OVERRIDES" in b
    assert "A1 or A2" in b
    assert "B1:" in b
    assert "B2:" in b
    assert "C1 or C2" in b
    assert '"du"' in b and '"Sie"' in b
    # The format guard is what makes it safe to append to a tool prompt.
    assert "DO NOT change" in b
    assert "correct" in b


# --- the DB-backed convenience ---------------------------------------------

def test_build_suffix_no_user_is_empty():
    assert build_adaptive_tool_suffix(None) == ""
    assert build_adaptive_tool_suffix(0) == ""


def test_build_suffix_no_level_is_empty(monkeypatch):
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": None})
    assert build_adaptive_tool_suffix(42) == ""


def test_build_suffix_with_level_uses_default(monkeypatch):
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": "A1"})
    # Every setting returns its shipped default, so the default behaviour text is used.
    monkeypatch.setattr("src.database.get_setting", lambda k, d="": d)
    suffix = build_adaptive_tool_suffix(7)
    assert "A1" in suffix
    assert "OVERRIDES" in suffix
    assert suffix.startswith("\n")


def test_build_suffix_reads_admin_behavior_override(monkeypatch):
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": "B2"})

    def fake_setting(key, default=""):
        if key == ADAPTIVE_TOOL_BEHAVIOR_SETTING:
            return "Custom expert wording for {level}."
        return default

    monkeypatch.setattr("src.database.get_setting", fake_setting)
    suffix = build_adaptive_tool_suffix(9)
    assert "Custom expert wording for B2." in suffix


def test_build_suffix_is_gated_on_the_trainer_when_a_workspace_is_given(monkeypatch):
    """Same gate the chat uses. The CEFR level is stored per user, so without it a
    national student who never enabled the Fachsprachentrainer would still get
    level-pitched cards while the chat answers plainly."""
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": "A1"})
    monkeypatch.setattr("src.database.get_setting", lambda k, d="": d)
    monkeypatch.setattr("src.database.is_language_training_active", lambda wid, uid: False)
    assert build_adaptive_tool_suffix(7, 3) == ""

    monkeypatch.setattr("src.database.is_language_training_active", lambda wid, uid: True)
    assert "A1" in build_adaptive_tool_suffix(7, 3)


def test_build_suffix_without_a_workspace_stays_ungated(monkeypatch):
    # Older queued tasks carry no workspace; they must keep working rather than
    # silently losing the adaptation.
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": "A1"})
    monkeypatch.setattr("src.database.get_setting", lambda k, d="": d)

    def boom(wid, uid):
        raise AssertionError("gate must not be consulted without a workspace")

    monkeypatch.setattr("src.database.is_language_training_active", boom)
    assert "A1" in build_adaptive_tool_suffix(7)


# --- wiring: the suffix reaches each tool's system prompt -------------------

def test_flashcards_system_prompt_carries_suffix(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_flashcards as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "cards": [{"begriff": "X", "definition": "Y"}]})
    client, calls = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    items, title = mod.generate_flashcards_from_source(client, "m", ctx, 1, locale="de", adaptive_suffix=MARKER)
    assert MARKER in _system_of(calls)
    assert items and title == "T"


def test_flashcards_empty_suffix_is_noop(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_flashcards as mod
    from src.tool_prompts import AIA_LERNKARTEN_PROMPT
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "cards": [{"begriff": "X", "definition": "Y"}]})
    client, calls = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    mod.generate_flashcards_from_source(client, "m", ctx, 1, locale="de", adaptive_suffix="")
    expected = AIA_LERNKARTEN_PROMPT.replace("{count}", "1").replace("{language}", mod._language_label("de"))
    assert _system_of(calls) == expected
    assert "ADAPT-MARKER" not in _system_of(calls)


def test_flashcards_carry_grammar_extras(monkeypatch):
    """word_class / singular / plural from the model land in the card's extras,
    so the frontend can show the Einzahl/Mehrzahl block."""
    from src.features.ai_assistant.tasks.language_training import _source_flashcards as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "cards": [{
        "begriff": "Brandverhütung", "definition": "Y",
        "word_parts": "Brand + Verhütung",
        "word_class": "Nomen", "singular": "die Brandverhütung", "plural": "die Brandverhütungen",
    }]})
    client, _ = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    items, _ = mod.generate_flashcards_from_source(client, "m", ctx, 1, locale="de", adaptive_suffix="")
    extras = items[0]["extras"]
    assert extras["word_class"] == "Nomen"
    assert extras["singular"] == "die Brandverhütung"
    assert extras["plural"] == "die Brandverhütungen"


def test_karteikarten_system_prompt_carries_suffix(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_cards as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "cards": [{"question": "Q", "answer": "A"}]})
    client, calls = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    items, title = mod.generate_cards_from_source(client, "m", ctx, 1, locale="de", adaptive_suffix=MARKER)
    assert MARKER in _system_of(calls)
    assert items


def test_quiz_system_prompt_carries_suffix(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}
    ]})
    client, calls = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    items, title = mod.generate_mc_from_source(client, "m", ctx, 1, locale="de", adaptive_suffix=MARKER)
    assert MARKER in _system_of(calls)
    assert items


def test_quiz_handles_both_question_and_gap_items(monkeypatch):
    """The standalone Lückentext tool is gone; the quiz produces comprehension
    questions AND gap sentences, and both must land in the same item shape."""
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Was ist X?", "options": ["a", "b", "c", "d"], "correct_idx": 1},
        {"sentence": "Der Prozess der ___ reduziert Redundanz.",
         "options": ["a", "b", "c", "d"], "correct_idx": 2},
    ]})
    client, calls = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    items, _ = mod.generate_mc_from_source(client, "m", ctx, 2, locale="de", adaptive_suffix=MARKER)
    assert MARKER in _system_of(calls)
    assert [i["front"] for i in items] == ["Was ist X?", "Der Prozess der ___ reduziert Redundanz."]
    # back is always the correct option, whichever kind the item is
    assert [i["back"] for i in items] == ["b", "c"]


def test_quiz_skips_items_with_a_broken_answer_index(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Gut?", "options": ["a", "b"], "correct_idx": 0},
        {"question": "Index daneben?", "options": ["a", "b"], "correct_idx": 7},
        {"question": "Ohne Optionen?", "options": [], "correct_idx": 0},
        {"options": ["a", "b"], "correct_idx": 0},
    ]})
    client, _ = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    items, _ = mod.generate_mc_from_source(client, "m", ctx, 4, locale="de")
    assert [i["front"] for i in items] == ["Gut?"]
