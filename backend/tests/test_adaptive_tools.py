"""Checks the level adaptation of the learning tools, component and wiring."""

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
    """A stub client that records the messages and always returns the same thing."""
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
    """The default overrides the tool rules but never changes count or solution."""
    b = DEFAULT_ADAPTIVE_TOOL_BEHAVIOR
    assert "OVERRIDES" in b
    # The levels come from the ladder, the text only names the placeholder.
    from src.services.aia_adaptive_tools import DESCRIPTION_PLACEHOLDER
    assert DESCRIPTION_PLACEHOLDER in b
    assert "C1 or C2" in b
    assert '"du"' in b and '"Sie"' in b
    # The format guard is what makes it safe to append to a tool prompt.
    assert "DO NOT change" in b
    assert "correct" in b


# --- the DB-backed convenience ---------------------------------------------

def test_build_suffix_no_user_is_empty():
    assert build_adaptive_tool_suffix(None) == ""
    assert build_adaptive_tool_suffix(0) == ""


def test_build_suffix_is_gated_on_the_person(monkeypatch):
    """Not ready means no block, whatever the stored level says."""
    monkeypatch.setattr("src.database.is_language_training_ready", lambda uid: False)
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": "A1"})
    assert build_adaptive_tool_suffix(42) == ""


def test_build_suffix_no_level_is_empty(monkeypatch):
    monkeypatch.setattr("src.database.is_language_training_ready", lambda uid: True)
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": None})
    assert build_adaptive_tool_suffix(42) == ""


def test_build_suffix_with_level_uses_default(monkeypatch):
    monkeypatch.setattr("src.database.is_language_training_ready", lambda uid: True)
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": "A1"})
    # Every setting returns its shipped default, so the default behaviour text is used.
    monkeypatch.setattr("src.database.get_setting", lambda k, d="": d)
    suffix = build_adaptive_tool_suffix(7)
    assert "A1" in suffix
    assert "OVERRIDES" in suffix
    assert suffix.startswith("\n")


def test_build_suffix_reads_admin_behavior_override(monkeypatch):
    monkeypatch.setattr("src.database.is_language_training_ready", lambda uid: True)
    monkeypatch.setattr("src.database.get_user_language_level", lambda uid: {"language_level": "B2"})

    def fake_setting(key, default=""):
        if key == ADAPTIVE_TOOL_BEHAVIOR_SETTING:
            return "Custom expert wording for {level}."
        return default

    monkeypatch.setattr("src.database.get_setting", fake_setting)
    suffix = build_adaptive_tool_suffix(9)
    assert "Custom expert wording for B2." in suffix


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
    from src.features.ai_assistant.prompts.language_training_prompts import (
        AIA_LERNKARTEN_PROMPT, COMPACT_JSON_RULE,
    )
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "cards": [{"begriff": "X", "definition": "Y"}]})
    client, calls = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    # The language now comes in with the job, not from a constant in the generator.
    mod.generate_flashcards_from_source(client, "m", ctx, 1, locale="de",
                                        language="German", adaptive_suffix="")
    expected = (AIA_LERNKARTEN_PROMPT.replace("{count}", "1").replace("{language}", "German")
                + COMPACT_JSON_RULE)
    assert _system_of(calls) == expected
    assert "ADAPT-MARKER" not in _system_of(calls)


def test_flashcards_carry_grammar_extras(monkeypatch):
    """Word class and forms from the model end up in the card's extras."""
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
    """The quiz delivers questions and gapped sentences in the same exercise shape."""
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


# --- wiring: the glossary route asks the gate for the person ----------------

def test_glossary_extract_asks_the_gate_for_the_person(monkeypatch):
    """The route passes the person, the gate itself knows no module any more."""
    import asyncio
    import types as _types
    from src.features.ai_assistant.routes import glossary as mod

    seen = {}

    def fake_suffix(user_id):
        seen["args"] = (user_id,)
        return ""

    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", fake_suffix)
    monkeypatch.setattr(mod.db, "get_aia_workspace", lambda uuid: {"id": 42, "user_id": 7})
    monkeypatch.setattr(mod.db, "is_student_enrolled", lambda wid, uid: True)
    monkeypatch.setattr(mod.db, "get_glossary_count", lambda wid, uid: 0)
    monkeypatch.setattr(mod.db, "get_aia_source", lambda uuid: {"id": 5, "workspace_id": 42})
    monkeypatch.setattr(mod.db, "get_aia_glossary_by_workspace", lambda wid, uid: [])
    monkeypatch.setattr(mod.db, "get_page_text", lambda sid, page: "")
    monkeypatch.setattr(mod.db, "bulk_create_glossary_entries", lambda *a, **k: None)
    monkeypatch.setattr(mod, "enforce_aia_burst", lambda uid, locale: None)
    monkeypatch.setattr(mod, "enforce_quota", lambda *a, **k: None)
    monkeypatch.setattr(mod, "is_admin_user", lambda u: False)

    content = json.dumps({"term_en": "exam work", "base_form": "Prüfungsleistung",
                          "definition": "d", "definition_en": "d",
                          "example_sentence": "s", "example_sentence_en": "s"})
    client, _ = _make_client(content)
    llm = _types.SimpleNamespace(_client=client, _model="m", _extra_body=None)
    body = _types.SimpleNamespace(text="Prüfungsleistung", source_uuid="u", page_number=1)

    asyncio.run(mod.extract_glossary_from_selection(
        "ws-uuid", body, {"user_id": 7}, llm, "de",
    ))
    assert seen["args"] == (7,)


# ─── Level ladder: the description comes from the ladder ─────────────────────

def test_tool_appendix_substitutes_the_description():
    from src.services.aia_adaptive_tools import adaptive_tool_appendix
    suffix, applied = adaptive_tool_appendix(
        "A2", "Stufe {level}: {description}", "", "Einfache Hauptsaetze."
    )
    assert "Stufe A2: Einfache Hauptsaetze." in suffix
    assert applied == "A2"


def test_tool_default_carries_the_description_placeholder():
    from src.services.aia_adaptive_tools import (
        DESCRIPTION_PLACEHOLDER,
        DEFAULT_ADAPTIVE_TOOL_BEHAVIOR,
    )
    assert DESCRIPTION_PLACEHOLDER in DEFAULT_ADAPTIVE_TOOL_BEHAVIOR


def test_tool_default_no_longer_carries_its_own_band_list():
    from src.services.aia_adaptive_tools import DEFAULT_ADAPTIVE_TOOL_BEHAVIOR
    b = DEFAULT_ADAPTIVE_TOOL_BEHAVIOR
    assert "- A1 or A2:" not in b
    assert "- B1:" not in b
    assert "- B2:" not in b
    assert "- C1 or C2:" not in b
    # The format rule stays, it is the real value of this text.
    assert "DO NOT change the requested number of items" in b
