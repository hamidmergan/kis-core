"""Set titles must not repeat inside one workspace.

Two mechanisms, both covered here:

* a do-not-repeat list in the generation prompt, which is only a request and is blind
  while another set of the same workspace is still generating;
* ``resolve_set_title``, which decides the final name AFTER generation from the set's own
  items, when the other set is finished and a clash is actually visible.

No DB and no network: the title calls run against a fake client.
"""

import json
import types

from src.features.ai_assistant.tasks.language_training._variation import (
    build_title_avoidance_block,
    is_title_taken,
    resolve_set_title,
    title_avoidance_block,
)

USED = ["Wissenschaftliches Arbeiten", "Wissenschaftliches Seminar"]

# Ein Grammatikthema in der Form, die die Generierung aus der Datenbank baut.
# Frueher kam dieses dict aus einem Code-Katalog, die Form ist absichtlich dieselbe
# geblieben, damit sich an den Generatoren keine Zeile aendern musste.
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

def test_no_titles_means_no_block():
    assert title_avoidance_block([]) == ""
    assert title_avoidance_block(["", "   "]) == ""


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


def test_no_workspace_yields_no_block():
    # Older queued tasks carry no workspace; they must keep generating.
    assert build_title_avoidance_block(None, "quiz") == ""
    assert build_title_avoidance_block(0, "quiz") == ""


def test_a_failing_query_never_breaks_generation(monkeypatch):
    def boom(workspace_id, tool):
        raise RuntimeError("db down")

    monkeypatch.setattr("src.database.get_recent_exercise_titles", boom)
    assert build_title_avoidance_block(3, "quiz") == ""


def test_block_is_read_per_workspace_and_tool(monkeypatch):
    seen = {}

    def fake(workspace_id, tool):
        seen["args"] = (workspace_id, tool)
        return USED

    monkeypatch.setattr("src.database.get_recent_exercise_titles", fake)
    block = build_title_avoidance_block(7, "grammatik")
    assert seen["args"] == (7, "grammatik")
    assert USED[0] in block


# --- what counts as the same title -------------------------------------------
#
# All three of these came out of one workspace and drove the two reported bugs.

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
    """The second reported bug: this got flagged as taken and was handed a pointless
    "(2)" although it was the first set with that name. A longer, more specific title
    is exactly what we want to keep."""
    assert not is_title_taken(SPECIFIC, [SEEN])


def test_a_genuinely_different_title_is_free():
    assert not is_title_taken("Meine Aufgaben vor der Abgabe", [SEEN])
    assert not is_title_taken("Literatursuche und Quellen", [SEEN])


def test_nothing_is_taken_against_an_empty_history():
    assert not is_title_taken(SEEN, [])
    assert not is_title_taken("", [SEEN])


# --- resolving the final title -----------------------------------------------

def test_the_title_comes_from_the_items_not_from_the_generation_call(monkeypatch):
    """The root cause of the repeats: the generation call sees the whole document and
    keeps naming the document. The proposed title is only a fallback now."""
    monkeypatch.setattr("src.database.get_recent_exercise_titles", lambda w, t, limit=100: [])
    client, calls = _make_client("Zitate richtig setzen")
    out = resolve_set_title(client, "m", 3, "grammatik", SEEN, ITEMS)
    assert out == "Zitate richtig setzen"
    assert len(calls) == 1


def test_the_proposed_title_is_used_when_the_title_call_gives_nothing(monkeypatch):
    monkeypatch.setattr("src.database.get_recent_exercise_titles", lambda w, t, limit=100: [])
    client, _ = _make_client("")
    assert resolve_set_title(client, "m", 3, "grammatik", SEEN, ITEMS) == SEEN


def test_a_taken_title_triggers_exactly_one_retry(monkeypatch):
    monkeypatch.setattr("src.database.get_recent_exercise_titles", lambda w, t, limit=100: [SEEN])
    client, calls = _make_client(NEAR, "Meine Aufgaben vor der Abgabe")
    out = resolve_set_title(client, "m", 3, "grammatik", SEEN, ITEMS)
    assert out == "Meine Aufgaben vor der Abgabe"
    assert len(calls) == 2


def test_the_retry_is_told_which_titles_are_taken(monkeypatch):
    monkeypatch.setattr("src.database.get_recent_exercise_titles", lambda w, t, limit=100: [SEEN])
    client, calls = _make_client(NEAR, "Etwas ganz Anderes")
    resolve_set_title(client, "m", 3, "grammatik", SEEN, ITEMS)
    assert SEEN in calls[1][0]["content"]


def test_the_counter_looks_at_the_whole_family_not_at_exact_matches(monkeypatch):
    """The first reported bug: two sets both ended in "(2)" because their bases differed
    by a letter and an exact comparison never saw the other one."""
    monkeypatch.setattr("src.database.get_recent_exercise_titles",
                        lambda w, t, limit=100: [SEEN, f"{SEEN} (2)"])
    client, _ = _make_client(NEAR, NEAR)  # both attempts land on a taken title
    assert resolve_set_title(client, "m", 3, "grammatik", SEEN, ITEMS) == f"{NEAR} (3)"


def test_the_counter_always_terminates(monkeypatch):
    monkeypatch.setattr("src.database.get_recent_exercise_titles", lambda w, t, limit=100: [SEEN])
    client, _ = _make_client(SEEN, SEEN)
    assert resolve_set_title(client, "m", 3, "grammatik", SEEN, ITEMS) == f"{SEEN} (2)"


def test_no_workspace_and_no_items_leave_the_proposed_title_alone(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not query without a workspace")

    monkeypatch.setattr("src.database.get_recent_exercise_titles", boom)
    client, calls = _make_client("x")
    assert resolve_set_title(client, "m", None, "quiz", "Titel", ITEMS) == "Titel"
    assert resolve_set_title(client, "m", 3, "quiz", "Titel", []) == "Titel"
    assert not calls


def test_a_failing_query_keeps_the_proposed_title(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr("src.database.get_recent_exercise_titles", boom)
    client, _ = _make_client("x")
    assert resolve_set_title(client, "m", 3, "quiz", "Titel", ITEMS) == "Titel"


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
    """The default is empty, so a first set in a fresh workspace is byte-identical
    to what the tool produced before."""
    from src.features.ai_assistant.tasks.language_training import _source_mc as mod
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    client, calls = _make_client(json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]}))
    mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="de")
    assert "TITLES ALREADY IN USE" not in _system_of(calls)
