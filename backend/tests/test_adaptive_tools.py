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


def test_glossary_flashcards_enrich_with_grammar_extras():
    """Glossary flashcards run through the same enrichment as source Lernkarten: the
    model's grammar extras land on the card and the definition is rewritten (no
    'term - ' prefix), while term/source page stay from the glossary index."""
    from src.features.ai_assistant.tasks.language_training._glossary import _generate_flashcards
    content = json.dumps({"title": "T", "cards": [{
        "begriff": "Normalisierung", "definition": "Einfach erklärt.",
        "word_parts": "Norm + al + isierung",
        "word_class": "Nomen", "singular": "die Normalisierung", "plural": "die Normalisierungen",
        "example_sentence": "Die Normalisierung ordnet Daten.",
    }]})
    client, calls = _make_client(content)
    selected = [{"term_de": "Normalisierung", "term_en": "Normalization",
                 "definition": "Alt", "filename": "f.pdf", "page_number": 3}]
    items = _generate_flashcards(client, "m", selected, "German", MARKER)
    assert MARKER in _system_of(calls)
    card = items[0]
    assert card["front"] == "Normalisierung"
    assert card["back"] == "Einfach erklärt."   # rewritten, no "Normalisierung - " prefix
    assert card["back_en"] == "Normalization"
    assert card["sources"][0]["page_number"] == 3
    assert card["extras"]["word_class"] == "Nomen"
    assert card["extras"]["singular"] == "die Normalisierung"
    assert card["extras"]["plural"] == "die Normalisierungen"


def test_glossary_flashcards_fall_back_to_plain_on_bad_json():
    """If enrichment fails, the card degrades to the plain definition (no prefix, no
    crash, no extras) so flashcards never break."""
    from src.features.ai_assistant.tasks.language_training._glossary import _generate_flashcards
    client, _ = _make_client("not json at all")
    selected = [{"term_de": "Satz", "term_en": "Sentence",
                 "definition": "Eine Aussage.", "filename": "f.pdf", "page_number": 1}]
    items = _generate_flashcards(client, "m", selected, "German", "")
    card = items[0]
    assert card["front"] == "Satz"
    assert card["back"] == "Eine Aussage."
    assert "extras" not in card


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


# --- glossary base form (Grundform / lemma of the marked term) --------------

def test_glossary_prompts_ask_for_the_base_form():
    """Both prompts must request base_form in their JSON shape and explain the
    lemma rule, so the marked word can be paired with its Grundform."""
    from src.features.ai_assistant.routes.glossary import (
        _GLOSSARY_SINGLE_PROMPT,
        _GLOSSARY_EXTRACT_PROMPT,
    )
    for p in (_GLOSSARY_SINGLE_PROMPT, _GLOSSARY_EXTRACT_PROMPT):
        assert "base_form" in p
        assert "singular nominative" in p and "infinitive" in p


def test_base_form_kept_when_it_differs_from_the_term():
    from src.features.ai_assistant.routes.glossary import _base_form
    assert _base_form("laufen", "läuft") == "laufen"
    assert _base_form("  Haus  ", "Häusern") == "Haus"


def test_base_form_dropped_when_equal_empty_or_missing():
    from src.features.ai_assistant.routes.glossary import _base_form
    # Equal to the marked word (case-insensitively) -> noise, drop it.
    assert _base_form("Arbeitsmarkt", "Arbeitsmarkt") == ""
    assert _base_form("laufen", "Laufen") == ""
    # Model returned nothing usable.
    assert _base_form("", "Haus") == ""
    assert _base_form("   ", "Haus") == ""
    assert _base_form(None, "Haus") == ""


# --- definition accuracy + document context ---------------------------------

def test_definition_prompts_demand_accuracy_over_plausibility():
    """The glossary-creation prompts (root) and the flashcard rewrite prompt must
    push for an accurate definition -- name the category, no invented specifics,
    no filler -- so a term like 'Wissenschaftliches Seminar' is not padded with
    plausible-but-wrong claims."""
    from src.features.ai_assistant.routes.glossary import (
        _GLOSSARY_SINGLE_PROMPT,
        _GLOSSARY_EXTRACT_PROMPT,
    )
    from src.tool_prompts import AIA_LERNKARTEN_PROMPT
    for p in (_GLOSSARY_SINGLE_PROMPT, _GLOSSARY_EXTRACT_PROMPT, AIA_LERNKARTEN_PROMPT):
        assert "category" in p
        assert "vague filler" in p
        assert "special case" in p


def test_single_term_prompt_offers_document_context():
    """Only the single-term prompt is fed a page excerpt (the multi-term path
    already carries the marked text), so only it must mention the CONTEXT block."""
    from src.features.ai_assistant.routes.glossary import (
        _GLOSSARY_SINGLE_PROMPT,
        _GLOSSARY_EXTRACT_PROMPT,
    )
    assert "CONTEXT" in _GLOSSARY_SINGLE_PROMPT
    assert "CONTEXT" not in _GLOSSARY_EXTRACT_PROMPT
    assert "marked text" in _GLOSSARY_EXTRACT_PROMPT


def test_context_snippet_centres_on_the_term():
    from src.features.ai_assistant.routes._helpers import _context_snippet
    page = ("A " * 300) + "the Widget is a small reusable part " + ("B " * 300)
    snip = _context_snippet(page, "Widget", max_chars=100)
    assert "Widget" in snip
    assert len(snip) <= 110  # max_chars plus the two ellipsis markers
    assert snip.startswith("… ") and snip.endswith(" …")


def test_context_snippet_short_page_returned_whole():
    from src.features.ai_assistant.routes._helpers import _context_snippet
    page = "Ein wissenschaftliches Seminar behandelt ein Thema in Referaten."
    assert _context_snippet(page, "Seminar", max_chars=700) == page


def test_context_snippet_falls_back_to_head_when_term_absent():
    from src.features.ai_assistant.routes._helpers import _context_snippet
    page = "word " * 400
    snip = _context_snippet(page, "notpresent", max_chars=80)
    assert snip.endswith("…")
    assert len(snip) <= 90


def test_context_snippet_empty_input_is_empty():
    from src.features.ai_assistant.routes._helpers import _context_snippet
    assert _context_snippet("", "x") == ""
    assert _context_snippet(None, "x") == ""


def test_flashcard_rewrite_forbids_inventing_beyond_the_given_definition():
    """The glossary flashcard enrichment must only simplify the stored definition,
    never add specifics or filler -- that is what turned a clean definition into
    'reden ueber aktuelle Forschung' / 'zeigen eigene Beitraege'."""
    from src.features.ai_assistant.tasks.language_training._glossary import _generate_flashcards
    client, calls = _make_client(json.dumps({"cards": []}))
    selected = [{"term_de": "Seminar", "term_en": "seminar",
                 "definition": "Ein Kurs.", "filename": "x.pdf", "page_number": 1}]
    _generate_flashcards(client, "m", selected, "German")
    user_msg = calls[0][1]["content"]
    assert "STRICTLY" in user_msg
    assert "not in the given definition" in user_msg
