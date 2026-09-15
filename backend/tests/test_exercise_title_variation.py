"""Set titles must not repeat inside a course room."""

import json
import types

from src.features.ai_assistant.tasks.language_training._variation import (
    _NAMING_RULE,
    build_title_avoidance_block,
    is_title_taken,
    resolve_set_title,
    title_avoidance_block,
)

USED = ["Wissenschaftliches Arbeiten", "Wissenschaftliches Seminar"]

# A grammar topic in the shape that comes from the database.
_TOPIC = {
    "id": 1,
    "label": "Passiv Präsens",
    "rule": "Input: an active sentence in the present tense. Output: the passive.",
    "example": {"before": "Hilde erklärt einen Begriff.",
                "after": "Ein Begriff wird von Hilde erklärt."},
    "examples": [{"before": "Hilde erklärt einen Begriff.",
                  "after": "Ein Begriff wird von Hilde erklärt."}],
}


def _make_client(*contents):
    """Fake client. Each call returns the next content, the last one repeats."""
    calls = []
    queue = list(contents) or [""]

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = queue[min(len(calls) - 1, len(queue) - 1)]
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _system_of(calls):
    return calls[0][0]["content"]


def _ctx():
    return types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")


# --- the prompt block --------------------------------------------------------

def test_without_taken_titles_only_the_naming_rule_remains():
    """The rule always travels, it is what replaced the separate title call."""
    assert title_avoidance_block([]) == _NAMING_RULE
    assert title_avoidance_block(["", "   "]) == _NAMING_RULE


def test_the_block_always_says_to_name_the_set_not_the_document():
    for block in (title_avoidance_block([]), title_avoidance_block(USED)):
        assert "TITLE OF THIS SET" in block
        assert "NEVER the document" in block


def test_block_lists_every_title_and_demands_a_different_one():
    block = title_avoidance_block(USED)
    assert block.startswith("\n\n")
    for title in USED:
        assert title in block
    assert "MUST differ" in block


def test_block_deduplicates_case_insensitively():
    block = title_avoidance_block(["Wissenschaft", "WISSENSCHAFT", "wissenschaft"])
    assert block.count("Wissenschaft") == 1


def test_block_is_capped_so_it_stays_a_footnote():
    block = title_avoidance_block([f"Titel {i}" for i in range(50)])
    assert block.count("\n  - ") == 10


def test_block_shortens_an_overlong_title():
    block = title_avoidance_block(["x" * 400])
    assert "x" * 400 not in block
    assert "x" * 90 in block


def test_no_workspace_still_yields_the_naming_rule():
    # Older queued tasks carry no workspace; they must still name the set.
    assert build_title_avoidance_block(None, "quiz") == _NAMING_RULE
    assert build_title_avoidance_block(0, "quiz") == _NAMING_RULE


def test_a_failing_query_never_breaks_generation(monkeypatch):
    def boom(workspace_id, tool):
        raise RuntimeError("db down")

    monkeypatch.setattr("src.database.get_recent_exercise_titles", boom)
    assert build_title_avoidance_block(3, "quiz") == _NAMING_RULE


def test_block_is_read_per_workspace_and_tool(monkeypatch):
    seen = {}

    def fake(workspace_id, tool):
        seen["args"] = (workspace_id, tool)
        return USED

    monkeypatch.setattr("src.database.get_recent_exercise_titles", fake)
    block = build_title_avoidance_block(7, "grammatik")
    assert seen["args"] == (7, "grammatik")
    assert USED[0] in block


# All three titles come from one course room and caused the reported bugs.

SEEN = "Wissenschaftliches Arbeiten im Seminar"
NEAR = "Wissenschaftliche Arbeiten im Seminar"          # one letter apart
SPECIFIC = "Wissenschaftliche Arbeiten im Seminar: Passiv üben"

ITEMS = [{"front": "Der Server speichert die Werte.", "back": "..."}]


def test_a_one_letter_variant_counts_as_taken():
    assert is_title_taken(NEAR, [SEEN])


def test_case_and_punctuation_do_not_make_a_title_new():
    assert is_title_taken("wissenschaftliches arbeiten, im seminar!", [SEEN])


def test_a_counted_title_belongs_to_its_own_family():
    # normalize() drops the bracketed counter, so "X (2)" is the same title as "X".
    assert is_title_taken(f"{SEEN} (2)", [SEEN])


def test_a_more_specific_title_is_its_own_title():
    """A longer, more precise title must not get a number."""
    assert not is_title_taken(SPECIFIC, [SEEN])


def test_a_genuinely_different_title_is_free():
    assert not is_title_taken("Meine Aufgaben vor der Abgabe", [SEEN])
    assert not is_title_taken("Literatursuche und Quellen", [SEEN])


def test_nothing_is_taken_against_an_empty_history():
    assert not is_title_taken(SEEN, [])
    assert not is_title_taken("", [SEEN])


# --- resolving the final title -----------------------------------------------
# The title comes out of the generation call, so resolving it costs no model call.

def test_the_title_of_the_generation_call_is_kept(monkeypatch):
    monkeypatch.setattr("src.database.get_recent_exercise_titles", lambda w, t, limit=100: [])
    assert resolve_set_title(3, "grammatik", "Zitate richtig setzen") == "Zitate richtig setzen"


def test_a_taken_title_is_numbered_instead_of_asked_again(monkeypatch):
    monkeypatch.setattr("src.database.get_recent_exercise_titles", lambda w, t, limit=100: [SEEN])
    assert resolve_set_title(3, "grammatik", NEAR) == f"{NEAR} (2)"


def test_the_counter_looks_at_the_whole_family_not_at_exact_matches(monkeypatch):
    """Two titles differing by one letter are one family."""
    monkeypatch.setattr("src.database.get_recent_exercise_titles",
                        lambda w, t, limit=100: [SEEN, f"{SEEN} (2)"])
    assert resolve_set_title(3, "grammatik", NEAR) == f"{NEAR} (3)"


def test_a_more_specific_title_keeps_its_own_name(monkeypatch):
    monkeypatch.setattr("src.database.get_recent_exercise_titles", lambda w, t, limit=100: [SEEN])
    assert resolve_set_title(3, "grammatik", SPECIFIC) == SPECIFIC


def test_no_workspace_and_no_title_leave_the_name_alone(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not query without a workspace")

    monkeypatch.setattr("src.database.get_recent_exercise_titles", boom)
    assert resolve_set_title(None, "quiz", "Titel") == "Titel"
    assert resolve_set_title(3, "quiz", "   ") == ""


def test_a_failing_query_keeps_the_generated_title(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr("src.database.get_recent_exercise_titles", boom)
    assert resolve_set_title(3, "quiz", "Titel") == "Titel"


# --- wiring: the block reaches every generator's system prompt ---------------

MARKER = "\n\nTITLES ALREADY IN USE in this workspace:\n  - Nur Dieser Eine"


def test_flashcards_prompt_carries_the_block(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_flashcards as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps(
        {"title": "T", "cards": [{"begriff": "X", "definition": "Y"}]}))
    mod.generate_flashcards_from_source(client, "m", _ctx(), 1, locale="de",
                                        title_avoidance=MARKER)
    assert MARKER in _system_of(calls)


def test_karteikarten_prompt_carries_the_block(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_cards as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps(
        {"title": "T", "cards": [{"question": "Q", "answer": "A"}]}))
    mod.generate_cards_from_source(client, "m", _ctx(), 1, locale="de",
                                   title_avoidance=MARKER)
    assert MARKER in _system_of(calls)


def test_quiz_prompt_carries_the_block(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]}))
    mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="de",
                                title_avoidance=MARKER)
    assert MARKER in _system_of(calls)


def test_grammar_prompt_carries_the_block(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_grammar as mod
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
    mod.generate_grammar_from_source(client, "m", _ctx(), _TOPIC, 2,
                                     locale="de", title_avoidance=MARKER)
    assert MARKER in _system_of(calls)


def test_generators_stay_unchanged_without_a_block(monkeypatch):
    """In a fresh course room everything stays as before."""
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]}))
    mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="de")
    assert "TITLES ALREADY IN USE" not in _system_of(calls)
