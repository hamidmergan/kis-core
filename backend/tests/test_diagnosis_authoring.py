"""Expert-authored diagnosis questions: data model, modes and deterministic grading.

The diagnosis moves from "one LLM call per question" to expert-authored items.
An option question carries its own options with a correct/incorrect flag, and is
graded in code (no model) by comparing the learner's picks to the correct set.
A free-text item carries the question text; it is still judged by the one final
LLM call. Eine unfertige Zeile gibt es nicht mehr: frueher schrieb das Modell die
Frage dann waehrend des Tests, heute faellt der ganze Plan auf den Standard zurueck.

These tests pin the parsing (backwards compatible with the old band/type/text
plans), the mode a slot resolves to, and the all-or-nothing grading.
"""

import json

import pytest

import random

from src.services.aia_diagnosis_chat import (
    CHOICE_TYPE,
    DEFAULT_GERMAN_QUESTION_PLAN,
    FREE_TEXT_TYPE,
    answered_items,
    build_grading_brief,
    correct_values,
    grade_selection,
    grade_typed,
    is_multi_correct,
    manual_question_payload,
    option_values,
    parse_question_plan,
    question_mode,
    question_plan_is_valid,
    wants_short_box,
    DiagnosisChatError,
)


# ─── Parsing: options + example, backwards compatible ──────────────────────

def test_parse_strips_a_legacy_band_from_a_written_out_plan():
    """Eine alte Zeile trug eine CEFR-Stufe; die faellt weg statt abgelehnt zu werden."""
    raw = json.dumps([
        {"band": "A1", "type": "gap fill", "text": "Ich ___ Student.", "answers": ["bin"]},
        {"band": "B2", "type": "free writing", "text": "Schreibe drei Sätze."},
    ])
    assert parse_question_plan(raw) == [
        {"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]},
        {"type": FREE_TEXT_TYPE, "text": "Schreibe drei Sätze."},
    ]


def test_parse_maps_the_six_old_names_onto_two_task_types():
    """Ein Plan aus der Zeit der sechs Arten oeffnet unveraendert. Die drei
    Auswahl-Namen waren im Code Wort fuer Wort dasselbe, und Lueckentext,
    Fehlerkorrektur und freies Schreiben unterschieden sich nur darin, ob eine
    Loesung dastand. Genau das bleibt erhalten, ohne Datenwanderung."""
    raw = json.dumps([
        {"type": CHOICE_TYPE, "text": "Q1",
         "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}]},
        {"type": "reading comprehension", "text": "Q2",
         "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}]},
        {"type": "situation", "text": "Q3",
         "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}]},
        {"type": "gap fill", "text": "Ich ___ Student.", "answers": ["bin"]},
        {"type": "error correction", "text": "Verbessere den Satz."},
        {"type": "free writing", "text": "Schreibe drei Sätze."},
    ])
    plan = parse_question_plan(raw)
    assert [step["type"] for step in plan] == [
        CHOICE_TYPE, CHOICE_TYPE, CHOICE_TYPE,
        FREE_TEXT_TYPE, FREE_TEXT_TYPE, FREE_TEXT_TYPE,
    ]
    # Und jede Zeile wird weiter genau so bewertet wie vorher.
    assert [question_mode(step) for step in plan] == [
        "manual_options", "manual_options", "manual_options",
        "manual_typed", "manual_text", "manual_text",
    ]


def test_parse_rejects_a_type_that_never_existed():
    assert parse_question_plan(json.dumps([{"type": "essay", "text": "Q"}])) \
        == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_accepts_options_with_correct_flags():
    raw = json.dumps([{
        "band": "A1", "type": CHOICE_TYPE,
        "text": "Ich ___ jeden Tag zur Arbeit.",
        "options": [
            {"text": "gehe", "correct": True},
            {"text": "gehst", "correct": False},
            {"text": "geht", "correct": False},
            {"text": "gehen", "correct": False},
        ],
    }])
    step = parse_question_plan(raw)[0]
    assert step["text"] == "Ich ___ jeden Tag zur Arbeit."
    assert step["options"] == [
        {"text": "gehe", "correct": True},
        {"text": "gehst", "correct": False},
        {"text": "geht", "correct": False},
        {"text": "gehen", "correct": False},
    ]


def test_parse_accepts_a_typed_answer_key():
    raw = json.dumps([{
        "type": FREE_TEXT_TYPE,
        "text": "Ich ___ jeden Tag zur Arbeit.",
        "answers": ["gehe", " fahre "],
    }])
    step = parse_question_plan(raw)[0]
    assert step["answers"] == ["gehe", "fahre"]
    assert "options" not in step


def test_parse_reads_a_legacy_gap_fill_with_options_as_an_answer_key():
    """Gap fill used to be an option type, so plans stored before typed answers
    hold four options. The correct ones become the solution instead of the row
    silently dropping back to a model-generated question."""
    raw = json.dumps([{
        "band": "A1", "type": "gap fill",
        "text": "Ich ___ jeden Tag zur Arbeit.",
        "options": [
            {"text": "gehe", "correct": True},
            {"text": "gehst", "correct": False},
            {"text": "geht", "correct": False},
            {"text": "gehen", "correct": False},
        ],
    }])
    step = parse_question_plan(raw)[0]
    assert step["answers"] == ["gehe"]
    assert "options" not in step


def test_parse_falls_back_on_an_empty_typed_answer_key():
    """Ein leeres Feld ist etwas anderes als ein leeres Array: wer gar keine
    Loesung will, laesst den Schluessel weg. Ein leeres Array ist kaputt."""
    raw = json.dumps([{"type": FREE_TEXT_TYPE, "text": "Q", "answers": []}])
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_falls_back_on_a_blank_typed_answer():
    raw = json.dumps([{"type": FREE_TEXT_TYPE, "text": "Q", "answers": ["gehe", "  "]}])
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_keeps_a_free_text_without_a_solution():
    """Die Loesung ist freiwillig. Ohne sie ist die Zeile fertig, nicht kaputt."""
    raw = json.dumps([{"type": FREE_TEXT_TYPE, "text": "Schreibe drei Sätze."}])
    assert parse_question_plan(raw) == [
        {"type": FREE_TEXT_TYPE, "text": "Schreibe drei Sätze."},
    ]


def test_parse_accepts_multiple_correct_options():
    raw = json.dumps([{
        "band": "A1", "type": CHOICE_TYPE, "text": "Was passt?",
        "options": [
            {"text": "eins", "correct": True},
            {"text": "zwei", "correct": True},
            {"text": "drei", "correct": False},
        ],
    }])
    assert correct_values(parse_question_plan(raw)[0]) == {"eins", "zwei"}


def test_parse_drops_a_free_text_example():
    """The per-question example is gone: the model calibrates free-text answers
    against the global CALIBRATION EXAMPLES, so a stored example is dropped."""
    raw = json.dumps([{
        "type": "error correction",
        "text": "Verbessere: Ich habe gegangen nach Hause.",
        "example": "Ich bin nach Hause gegangen.",
    }])
    step = parse_question_plan(raw)[0]
    assert "example" not in step
    assert step["text"] == "Verbessere: Ich habe gegangen nach Hause."


def test_parse_falls_back_to_default_on_options_without_a_correct_one():
    """A single structural problem reverts the whole plan to the shipped default,
    so the diagnosis always runs on a usable plan (existing philosophy)."""
    raw = json.dumps([{
        "band": "A1", "type": CHOICE_TYPE, "text": "Q",
        "options": [{"text": "a", "correct": False}, {"text": "b", "correct": False}],
    }])
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_falls_back_on_option_with_empty_text():
    raw = json.dumps([{
        "band": "A1", "type": CHOICE_TYPE, "text": "Q",
        "options": [{"text": "", "correct": True}, {"text": "b", "correct": False}],
    }])
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_falls_back_on_too_few_options():
    raw = json.dumps([{
        "band": "A1", "type": CHOICE_TYPE, "text": "Q",
        "options": [{"text": "only", "correct": True}],
    }])
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_drops_options_on_free_text_types():
    """Optionen ergeben an einem Freitext keinen Sinn und fallen weg, statt den
    Plan zu kippen, damit ein liegengebliebenes Feld aus dem Editor nicht stoert."""
    raw = json.dumps([{
        "band": "B2", "type": FREE_TEXT_TYPE, "text": "Schreib was.",
        "options": [{"text": "x", "correct": True}, {"text": "y", "correct": False}],
    }])
    step = parse_question_plan(raw)[0]
    assert "options" not in step
    assert step["text"] == "Schreib was."


# ─── Question mode ─────────────────────────────────────────────────────────

def test_mode_manual_options_needs_text_and_options():
    step = {"band": "A1", "type": CHOICE_TYPE, "text": "Q",
            "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}]}
    assert question_mode(step) == "manual_options"


def test_mode_manual_typed_needs_text_and_a_solution():
    step = {"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]}
    assert question_mode(step) == "manual_typed"


def test_mode_manual_text_for_free_text_with_text():
    step = {"band": "A2", "type": FREE_TEXT_TYPE, "text": "Verbessere: ..."}
    assert question_mode(step) == "manual_text"


def test_mode_follows_the_solution_not_the_name():
    """Der eigentliche Punkt der Zusammenlegung: bei einem Freitext entscheidet
    die Loesung, wer bewertet, nicht die Aufgabenart. Mit Loesung prueft der Code,
    ohne Loesung liest die KI. Ein vierter Modus, in dem das Modell die Frage
    waehrend des Tests schreibt, ist entfallen."""
    assert question_mode({"type": CHOICE_TYPE, "text": "Q"}) == "manual_options"
    assert question_mode({"type": FREE_TEXT_TYPE, "text": "Q", "answers": ["x"]}) == "manual_typed"
    assert question_mode({"type": FREE_TEXT_TYPE, "text": "Q"}) == "manual_text"


# ─── Deterministic grading (all-or-nothing) ────────────────────────────────

def _opt_step(*pairs):
    return {"band": "A1", "type": CHOICE_TYPE, "text": "Q",
            "options": [{"text": t, "correct": c} for t, c in pairs]}


def test_grade_single_correct_hit():
    step = _opt_step(("gehe", True), ("gehst", False), ("geht", False))
    assert grade_selection(step, ["gehe"]) is True


def test_grade_single_correct_miss():
    step = _opt_step(("gehe", True), ("gehst", False), ("geht", False))
    assert grade_selection(step, ["gehst"]) is False


def test_grade_ignores_whitespace_around_selection():
    step = _opt_step(("gehe", True), ("gehst", False))
    assert grade_selection(step, ["  gehe "]) is True


def test_grade_is_case_sensitive_for_the_deterministic_path():
    """Exact match only. Anything fuzzy is left to the final LLM, so the code
    path never guesses; 'Gehe' vs 'gehe' is not a clean hit."""
    step = _opt_step(("gehe", True), ("gehst", False))
    assert grade_selection(step, ["Gehe"]) is False


def test_grade_multi_all_correct_hit():
    step = _opt_step(("eins", True), ("zwei", True), ("drei", False))
    assert grade_selection(step, ["eins", "zwei"]) is True
    assert grade_selection(step, ["zwei", "eins"]) is True  # order does not matter


def test_grade_multi_missing_one_is_wrong():
    step = _opt_step(("eins", True), ("zwei", True), ("drei", False))
    assert grade_selection(step, ["eins"]) is False


def test_grade_multi_extra_wrong_pick_is_wrong():
    step = _opt_step(("eins", True), ("zwei", True), ("drei", False))
    assert grade_selection(step, ["eins", "zwei", "drei"]) is False


def test_grade_empty_selection_is_wrong():
    step = _opt_step(("eins", True), ("zwei", False))
    assert grade_selection(step, []) is False


def test_grade_duplicate_selection_does_not_break_all_or_nothing():
    step = _opt_step(("eins", True), ("zwei", False))
    assert grade_selection(step, ["eins", "eins"]) is True


def test_is_multi_correct():
    assert is_multi_correct(_opt_step(("a", True), ("b", True))) is True
    assert is_multi_correct(_opt_step(("a", True), ("b", False))) is False


def test_option_values_are_authoring_order_without_flags():
    step = _opt_step(("gehe", True), ("gehst", False), ("geht", False))
    assert option_values(step) == ["gehe", "gehst", "geht"]


# ─── Typed answers (gap fill): forgiving where it carries no meaning ────────

def _gap_step(*answers):
    return {"type": FREE_TEXT_TYPE, "text": "Ich ___ jeden Tag zur Arbeit.",
            "answers": list(answers)}


def test_grade_typed_exact_hit():
    assert grade_typed(_gap_step("gehe"), "gehe") is True


def test_grade_typed_miss():
    assert grade_typed(_gap_step("gehe"), "geht") is False


def test_grade_typed_ignores_case_and_surrounding_whitespace():
    """Capitalisation and a stray space are typing, not language, so they never
    decide the answer."""
    assert grade_typed(_gap_step("gehe"), "  Gehe ") is True


def test_grade_typed_ignores_a_trailing_full_stop():
    assert grade_typed(_gap_step("gehe"), "gehe.") is True


def test_grade_typed_keeps_umlauts_significant():
    """Letters themselves are language: a missing umlaut stays a mistake, and the
    forgiving comparison never quietly folds it away."""
    assert grade_typed(_gap_step("Käse"), "Kase") is False
    assert grade_typed(_gap_step("Straße"), "Strasse") is False


def test_grade_typed_accepts_any_listed_spelling():
    step = _gap_step("Straße", "Strasse")
    assert grade_typed(step, "Strasse") is True
    assert grade_typed(step, "straße") is True


def test_grade_typed_collapses_inner_whitespace():
    assert grade_typed(_gap_step("je desto"), "je   desto") is True


def test_grade_typed_skipped_answer_is_wrong():
    assert grade_typed(_gap_step("gehe"), "") is False


def test_grade_typed_without_a_key_is_never_correct():
    assert grade_typed({"type": FREE_TEXT_TYPE, "text": "Q"}, "gehe") is False


# ─── Client payloads: never leak the answer key ────────────────────────────

def test_manual_option_payload_hides_correct_flags_and_shuffles():
    step = {"band": "A1", "type": CHOICE_TYPE, "text": "Ich ___ Student.",
            "options": [{"text": "bin", "correct": True},
                        {"text": "ist", "correct": False},
                        {"text": "sind", "correct": False},
                        {"text": "seid", "correct": False}]}
    payload = manual_question_payload(step, rng=random.Random(1))
    assert payload["done"] is False
    assert payload["message"] == "Ich ___ Student."
    assert payload["multi"] is False
    # Every value present, but no correctness signal reaches the client.
    assert sorted(payload["options"]) == ["bin", "ist", "seid", "sind"]
    assert "correct" not in str(payload["options"])


def test_manual_typed_payload_keeps_the_solution_server_side():
    """The learner types, so shipping the key would hand them the answer. Only the
    question and the one-line hint travel."""
    step = {"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]}
    payload = manual_question_payload(step)
    assert payload == {"done": False, "message": "Ich ___ Student.", "short": True}
    assert "bin" not in str(payload["message"])


def test_a_long_solution_keeps_the_big_answer_box():
    """Die Feldgroesse hing frueher am Typ 'gap fill'. Den gibt es nicht mehr, also
    sagt die Loesung es: ein Wort heisst einzeilig, ein ganzer richtiger Satz
    (etwa bei einer Fehlerkorrektur mit Loesung) heisst grosses Feld."""
    long_step = {"type": FREE_TEXT_TYPE, "text": "Verbessere den Satz.",
                 "answers": ["Gestern habe ich einen sehr langen Film gesehen."]}
    assert wants_short_box(long_step) is False
    assert "short" not in manual_question_payload(long_step)
    assert wants_short_box({"type": FREE_TEXT_TYPE, "text": "Q", "answers": ["gehe"]}) is True
    assert wants_short_box({"type": FREE_TEXT_TYPE, "text": "Q"}) is False


def test_manual_option_payload_marks_multi():
    step = {"band": "A1", "type": CHOICE_TYPE, "text": "Q",
            "options": [{"text": "a", "correct": True},
                        {"text": "b", "correct": True},
                        {"text": "c", "correct": False}]}
    assert manual_question_payload(step)["multi"] is True


def test_manual_free_text_payload_has_no_options():
    step = {"band": "B2", "type": FREE_TEXT_TYPE, "text": "Schreib drei Sätze."}
    payload = manual_question_payload(step)
    assert payload == {"done": False, "message": "Schreib drei Sätze."}


# ─── Transcript pairing + grading brief ────────────────────────────────────

def test_answered_items_pairs_questions_with_answers():
    history = [
        {"role": "assistant", "content": "Frage 1", "options": ["a", "b"]},
        {"role": "user", "content": "a", "selected": ["a"]},
        {"role": "assistant", "content": "Frage 2"},
        {"role": "user", "content": "meine Antwort"},
        {"role": "assistant", "content": "Frage 3 (unbeantwortet)"},
    ]
    items = answered_items(history)
    assert len(items) == 2  # the trailing unanswered question is ignored
    assert items[0]["selected"] == ["a"]
    assert items[0]["options"] == ["a", "b"]
    assert items[1]["selected"] is None
    assert items[1]["answer"] == "meine Antwort"


def test_grading_brief_gives_a_fixed_result_for_clean_authored_picks():
    plan = [{"band": "A1", "type": CHOICE_TYPE, "text": "Ich ___ Student.",
             "options": [{"text": "bin", "correct": True},
                         {"text": "ist", "correct": False}]}]
    history = [
        {"role": "assistant", "content": "Ich ___ Student.", "options": ["ist", "bin"]},
        {"role": "user", "content": "bin", "selected": ["bin"]},
    ]
    brief = build_grading_brief(plan, history)
    assert "RESULT (already graded" in brief
    assert "CORRECT" in brief
    assert "bin" in brief


def test_grading_brief_marks_a_wrong_authored_pick_incorrect():
    plan = [{"band": "A1", "type": CHOICE_TYPE, "text": "Q",
             "options": [{"text": "bin", "correct": True},
                         {"text": "ist", "correct": False}]}]
    history = [
        {"role": "assistant", "content": "Q", "options": ["ist", "bin"]},
        {"role": "user", "content": "ist", "selected": ["ist"]},
    ]
    assert "INCORRECT" in build_grading_brief(plan, history)


def test_grading_brief_grades_a_typed_gap_fill_in_code():
    plan = [{"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]}]
    history = [
        {"role": "assistant", "content": "Ich ___ Student."},
        {"role": "user", "content": "Bin."},
    ]
    brief = build_grading_brief(plan, history)
    assert "RESULT (already graded" in brief
    assert "CORRECT" in brief and "INCORRECT" not in brief


def test_grading_brief_marks_a_wrong_typed_gap_fill_incorrect():
    plan = [{"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]}]
    history = [
        {"role": "assistant", "content": "Ich ___ Student."},
        {"role": "user", "content": "ist"},
    ]
    assert "INCORRECT" in build_grading_brief(plan, history)


def test_grading_brief_marks_a_missed_gap_fill_incorrect():
    """Der Loesungsschluessel ist immer da, also steht das Urteil im Bericht fest."""
    plan = [{"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]}]
    history = [
        {"role": "assistant", "content": "Ich ___ Student."},
        {"role": "user", "content": "ist"},
    ]
    brief = build_grading_brief(plan, history)
    assert "RESULT (already graded in code, use exactly this): INCORRECT." in brief


def test_grading_brief_defers_free_worded_pick_to_the_model():
    plan = [{"band": "A1", "type": CHOICE_TYPE, "text": "Q",
             "options": [{"text": "bin", "correct": True},
                         {"text": "ist", "correct": False}]}]
    history = [
        {"role": "assistant", "content": "Q", "options": ["ist", "bin"]},
        {"role": "user", "content": "ich glaube eher bin"},
    ]
    brief = build_grading_brief(plan, history)
    assert "free words" in brief
    assert "RESULT" not in brief  # not code-graded, the model decides
    # The answer key is present so the model can judge, but it stays server-side.
    assert "Correct answer(s): ['bin']" in brief


def test_grading_brief_for_free_text_has_no_example_line():
    """The per-question example is gone; the brief just asks the model to judge the
    answer's level (against the global calibration examples in the system prompt)."""
    plan = [{"type": FREE_TEXT_TYPE, "text": "Verbessere: Ich habe gegangen."}]
    history = [
        {"role": "assistant", "content": "Verbessere: Ich habe gegangen."},
        {"role": "user", "content": "Ich bin gegangen."},
    ]
    brief = build_grading_brief(plan, history)
    assert "A good answer looks like" not in brief
    assert "Judge the answer for its language level" in brief
    assert "Ich bin gegangen." in brief


# ─── Default resolution ────────────────────────────────────────────────────

def test_no_stored_plan_uses_the_shipped_german_set():
    assert parse_question_plan("") is DEFAULT_GERMAN_QUESTION_PLAN
    assert parse_question_plan("   ") is DEFAULT_GERMAN_QUESTION_PLAN


def test_a_stored_admin_plan_wins_over_the_default():
    import json as _json
    stored = _json.dumps([{"type": FREE_TEXT_TYPE, "text": "Schreib was."}])
    assert parse_question_plan(stored) == [{"type": FREE_TEXT_TYPE, "text": "Schreib was."}]


# ─── Save-path validation ──────────────────────────────────────────────────

def test_plan_is_valid_accepts_old_and_new_shapes():
    """Struktur-Pruefung. Ob eine Zeile fertig ist, prueft first_incomplete_question
    (siehe test_diagnosis_plan_complete)."""
    import json as _json
    assert question_plan_is_valid(_json.dumps([{"band": "A1", "type": "gap fill"}]))
    assert question_plan_is_valid(_json.dumps([{
        "band": "A1", "type": CHOICE_TYPE, "text": "Q",
        "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}],
    }]))
    assert question_plan_is_valid(_json.dumps([{
        "type": "gap fill", "text": "Q", "answers": ["gehe"],
    }]))
    # A gap fill saved as an option question still saves: the runtime reads its
    # correct options as the solution rather than rejecting the whole plan.
    assert question_plan_is_valid(_json.dumps([{
        "band": "A1", "type": "gap fill", "text": "Q",
        "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}],
    }]))


def test_plan_is_valid_rejects_a_broken_solution():
    import json as _json
    assert not question_plan_is_valid(_json.dumps([{
        "type": FREE_TEXT_TYPE, "text": "Q", "answers": [],
    }]))
    assert not question_plan_is_valid(_json.dumps([{
        "type": FREE_TEXT_TYPE, "text": "Q", "answers": ["gehe", 7],
    }]))


def test_plan_is_valid_accepts_a_free_text_without_a_solution():
    """Kein Loesungsschluessel heisst: die KI beurteilt das. Das ist der Normalfall
    und darf nicht am Speicherweg scheitern."""
    import json as _json
    assert question_plan_is_valid(_json.dumps([{
        "type": FREE_TEXT_TYPE, "text": "Schreibe drei Sätze.",
    }]))


def test_plan_is_valid_rejects_muck():
    import json as _json
    assert not question_plan_is_valid("{not json")
    assert not question_plan_is_valid(_json.dumps([]))
    assert not question_plan_is_valid(_json.dumps([{"type": "essay"}]))
    assert not question_plan_is_valid(_json.dumps([{
        "type": "gap fill",
        "options": [{"text": "only", "correct": False}, {"text": "b", "correct": False}],
    }]))
    assert not question_plan_is_valid(_json.dumps([{"type": "free text", "text": 7}]))


# ─── The shipped German set is well-formed and fully authored ──────────────

def test_german_default_uses_both_task_types():
    types = [s["type"] for s in DEFAULT_GERMAN_QUESTION_PLAN]
    assert set(types) == {CHOICE_TYPE, FREE_TEXT_TYPE}
    # No question carries a band any more: level is read from the answers.
    assert all("band" not in s for s in DEFAULT_GERMAN_QUESTION_PLAN)


def test_german_default_has_no_auto_slots():
    """Jede Zeile ist fertig ausgeschrieben, also kostet eine deutsche Einstufung
    null Aufrufe fuer Fragen: Auswahl ist manual_options, Freitext mit Loesung ist
    manual_typed, Freitext ohne Loesung ist manual_text."""
    for step in DEFAULT_GERMAN_QUESTION_PLAN:
        if step["type"] == CHOICE_TYPE:
            assert question_mode(step) == "manual_options"
        elif step.get("answers"):
            assert question_mode(step) == "manual_typed"
        else:
            assert question_mode(step) == "manual_text"


def test_german_default_free_text_never_carries_options():
    for step in DEFAULT_GERMAN_QUESTION_PLAN:
        if step["type"] == FREE_TEXT_TYPE:
            assert "options" not in step, step["text"]


def test_german_default_option_slots_are_single_correct():
    for step in DEFAULT_GERMAN_QUESTION_PLAN:
        if step["type"] == CHOICE_TYPE:
            assert len(correct_values(step)) == 1, step["text"]


def test_german_default_round_trips_through_parse_and_validation():
    import json as _json
    raw = _json.dumps(DEFAULT_GERMAN_QUESTION_PLAN)
    assert question_plan_is_valid(raw)
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


# ─── Free-text minimum (save-path policy, separate from structural validity) ─

def test_count_judged_questions_ignores_free_text_with_a_solution():
    """Gezaehlt wird nur, was die KI wirklich liest. Ein Lueckensatz mit Loesung
    ist keine Schreibprobe, auch wenn er im selben Aufgabentyp steckt."""
    from src.services.aia_diagnosis_chat import count_judged_questions
    plan = [
        {"type": FREE_TEXT_TYPE, "text": "Ich ___ da.", "answers": ["bin"]},
        {"type": FREE_TEXT_TYPE, "text": "Verbessere den Satz."},
        {"type": FREE_TEXT_TYPE, "text": "Schreibe drei Sätze."},
    ]
    assert count_judged_questions(plan) == 2
    assert count_judged_questions([{"type": CHOICE_TYPE, "text": "Q"}]) == 0


def test_plan_needs_at_least_two_free_text():
    import json as _json
    from src.services.aia_diagnosis_chat import question_plan_has_enough_free_text
    choice = {"type": CHOICE_TYPE, "text": "Q",
              "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}]}
    too_few = _json.dumps([
        {"type": FREE_TEXT_TYPE, "text": "Ich ___ da.", "answers": ["bin"]},
        choice,
        {"type": FREE_TEXT_TYPE, "text": "Verbessere den Satz."},
    ])
    enough = _json.dumps([
        {"type": FREE_TEXT_TYPE, "text": "Verbessere den Satz."},
        {"type": FREE_TEXT_TYPE, "text": "Schreibe drei Sätze."},
    ])
    assert not question_plan_has_enough_free_text(too_few)
    assert question_plan_has_enough_free_text(enough)


def test_a_solution_on_every_free_text_fails_the_minimum():
    """Der Weg, auf dem man die Pflicht-Schreibproben aus Versehen loswird: ueberall
    eine Loesung eintragen. Dann prueft nur noch der Code und die Stufe hinge an
    nichts."""
    import json as _json
    from src.services.aia_diagnosis_chat import question_plan_has_enough_free_text
    all_solved = _json.dumps([
        {"type": FREE_TEXT_TYPE, "text": "Ich ___ da.", "answers": ["bin"]},
        {"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]},
        {"type": FREE_TEXT_TYPE, "text": "Er ___ Arzt.", "answers": ["ist"]},
    ])
    assert not question_plan_has_enough_free_text(all_solved)


def test_the_minimum_still_reads_a_plan_written_with_the_old_names():
    """Ein gespeicherter Plan von vor der Zusammenlegung darf nicht ploetzlich
    durchfallen, wenn die Verwaltung ihn nur oeffnet und wieder speichert."""
    import json as _json
    from src.services.aia_diagnosis_chat import question_plan_has_enough_free_text
    old = _json.dumps([
        {"type": "gap fill", "text": "Ich ___ da.", "answers": ["bin"]},
        {"type": "error correction", "text": "Verbessere den Satz."},
        {"type": "free writing", "text": "Schreibe drei Sätze."},
    ])
    assert question_plan_has_enough_free_text(old)


def test_plan_free_text_check_is_robust_to_muck():
    from src.services.aia_diagnosis_chat import question_plan_has_enough_free_text
    assert not question_plan_has_enough_free_text("{not json")
    assert not question_plan_has_enough_free_text('{"not": "a list"}')


def test_the_shipped_plan_meets_the_free_text_minimum():
    """Regression: the default must never dip below the enforced floor, or a fresh
    install would ship a plan the save path would then reject."""
    import json as _json
    from src.services.aia_diagnosis_chat import (
        question_plan_has_enough_free_text, DEFAULT_GERMAN_QUESTION_PLAN,
    )
    assert question_plan_has_enough_free_text(_json.dumps(DEFAULT_GERMAN_QUESTION_PLAN))
