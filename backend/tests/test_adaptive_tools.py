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
    items, title = mod.generate_mc_from_source(client, "m", ctx, "quiz", 1, locale="de", adaptive_suffix=MARKER)
    assert MARKER in _system_of(calls)
    assert items


def test_lueckentext_system_prompt_carries_suffix(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"sentence": "S ___", "answer": "a", "options": ["a", "b", "c", "d"], "correct_idx": 0}
    ]})
    client, calls = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")
    items, title = mod.generate_mc_from_source(client, "m", ctx, "lueckentext", 1, locale="de", adaptive_suffix=MARKER)
    assert MARKER in _system_of(calls)
    assert items


def test_glossary_lueckentext_system_prompt_carries_suffix():
    from src.features.ai_assistant.tasks.language_training._glossary import _generate_lueckentext
    content = json.dumps([
        {"sentence": "S ___", "answer": "a", "options": ["a", "b", "c", "d"], "correct_idx": 0, "term_de": "T"}
    ])
    client, calls = _make_client(content)
    selected = [{"term_de": "T", "term_en": "Te", "definition": "D", "filename": "f.pdf", "page_number": 1}]
    items = _generate_lueckentext(client, "m", selected, 1, "German", MARKER)
    assert MARKER in _system_of(calls)
    assert items


def test_glossary_vokabeltest_system_prompt_carries_suffix():
    from src.features.ai_assistant.tasks.language_training._glossary import _generate_vokabeltest
    content = json.dumps([
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0, "explanation": "E", "term_de": "T"}
    ])
    client, calls = _make_client(content)
    selected = [{"term_de": "T", "term_en": "Te", "definition": "D", "filename": "f.pdf", "page_number": 1}]
    items = _generate_vokabeltest(client, "m", selected, 1, "German", MARKER)
    assert MARKER in _system_of(calls)
    assert items


# --- glossary CREATION: definitions written at the learner's level ----------
# The glossary definition is authored once, when a term is added; adapting there
# is what actually makes glossary-derived Lernkarten/Karteikarten level-correct,
# since those copy the stored definition verbatim.

def test_glossary_creation_default_is_b1_no_suffix():
    from src.features.ai_assistant.routes.glossary import _glossary_system_prompt
    single = _glossary_system_prompt(True, "")
    extract = _glossary_system_prompt(False, "")
    # Default stays B1, and nothing extra is appended.
    assert "B1" in single and "B1" in extract
    assert "ADAPT-MARKER" not in single and "ADAPT-MARKER" not in extract
    # Single-term vs. multi-term extraction pick different base prompts.
    assert "ONE specific term" in single
    assert "JSON array" in extract


def test_glossary_creation_appends_suffix_when_level_exists():
    from src.features.ai_assistant.routes.glossary import _glossary_system_prompt
    assert MARKER in _glossary_system_prompt(True, MARKER)
    assert MARKER in _glossary_system_prompt(False, MARKER)


def test_glossary_prompts_announce_the_adaptive_override():
    """Both base prompts keep B1 as the default AND tell the model that an
    adaptive block, when present, overrides it -- so the appended suffix wins."""
    from src.features.ai_assistant.routes.glossary import (
        _GLOSSARY_SINGLE_PROMPT,
        _GLOSSARY_EXTRACT_PROMPT,
    )
    for p in (_GLOSSARY_SINGLE_PROMPT, _GLOSSARY_EXTRACT_PROMPT):
        assert "B1 level BY DEFAULT" in p
        assert "adaptive block" in p
