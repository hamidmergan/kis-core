"""Hand-written assessment questions: data model, modes and grading in code."""

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
    """An old row carried a CEFR level, that is dropped instead of rejected."""
    raw = json.dumps([
        {"band": "A1", "type": "gap fill", "text": "Ich ___ Student.", "answers": ["bin"]},
        {"band": "B2", "type": "free writing", "text": "Schreibe drei Sätze."},
    ])
    assert parse_question_plan(raw) == [
        {"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]},
        {"type": FREE_TEXT_TYPE, "text": "Schreibe drei Sätze."},
    ]


def test_parse_maps_the_six_old_names_onto_two_task_types():
    """A plan from the era of the six kinds opens unchanged."""
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
    # And every row is still graded exactly as before.
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
    """For an old cloze the correct options become the answer key."""
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
    """No field is something different from an empty field."""
    raw = json.dumps([{"type": FREE_TEXT_TYPE, "text": "Q", "answers": []}])
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_falls_back_on_a_blank_typed_answer():
    raw = json.dumps([{"type": FREE_TEXT_TYPE, "text": "Q", "answers": ["gehe", "  "]}])
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_keeps_a_free_text_without_a_solution():
    """The answer key is optional, without it the row is finished, not broken."""
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
    """The per-question example is gone, calibration happens globally."""
    raw = json.dumps([{
        "type": "error correction",
        "text": "Verbessere: Ich habe gegangen nach Hause.",
        "example": "Ich bin nach Hause gegangen.",
    }])
    step = parse_question_plan(raw)[0]
    assert "example" not in step
    assert step["text"] == "Verbessere: Ich habe gegangen nach Hause."


def test_parse_falls_back_to_default_on_options_without_a_correct_one():
    """A single malformed row resets the whole plan to the default."""
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
    """Options on a free text are dropped instead of toppling the plan."""
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
    """For a free text the answer key decides who grades."""
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
    """Exact matches only, everything fuzzy is read by the AI."""
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
    """Capitalisation and a space are typing, not language."""
    assert grade_typed(_gap_step("gehe"), "  Gehe ") is True


def test_grade_typed_ignores_a_trailing_full_stop():
    assert grade_typed(_gap_step("gehe"), "gehe.") is True


def test_grade_typed_keeps_umlauts_significant():
    """A missing umlaut stays a mistake."""
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
    """The answer key stays on the server, the learner types."""
    step = {"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]}
    payload = manual_question_payload(step)
    assert payload == {"done": False, "message": "Ich ___ Student.", "short": True}
    assert "bin" not in str(payload["message"])


def test_a_long_solution_keeps_the_big_answer_box():
    """The answer decides whether the field is single-line."""
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
    """The answer key is always there, so the verdict in the report is fixed."""
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
    """Without a per-question example the model judges against the global examples."""
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
    """Structure check, completeness is checked by another function."""
    import json as _json
    assert question_plan_is_valid(_json.dumps([{"band": "A1", "type": "gap fill"}]))
    assert question_plan_is_valid(_json.dumps([{
        "band": "A1", "type": CHOICE_TYPE, "text": "Q",
        "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}],
    }]))
    assert question_plan_is_valid(_json.dumps([{
        "type": "gap fill", "text": "Q", "answers": ["gehe"],
    }]))
    # An old cloze as a choice question can still be saved.
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
    """No answer key is the normal case and must not fail."""
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
    """Every row is spelled out, an assessment costs no question call."""
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
    """Only what the AI really reads is counted."""
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
    """Putting an answer key everywhere would defeat the mandatory writing samples."""
    import json as _json
    from src.services.aia_diagnosis_chat import question_plan_has_enough_free_text
    all_solved = _json.dumps([
        {"type": FREE_TEXT_TYPE, "text": "Ich ___ da.", "answers": ["bin"]},
        {"type": FREE_TEXT_TYPE, "text": "Ich ___ Student.", "answers": ["bin"]},
        {"type": FREE_TEXT_TYPE, "text": "Er ___ Arzt.", "answers": ["ist"]},
    ])
    assert not question_plan_has_enough_free_text(all_solved)


def test_the_minimum_still_reads_a_plan_written_with_the_old_names():
    """An old plan must not fail on merely opening and saving it."""
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
    """The default must never fall below the enforced floor."""
    import json as _json
    from src.services.aia_diagnosis_chat import (
        question_plan_has_enough_free_text, DEFAULT_GERMAN_QUESTION_PLAN,
    )
    assert question_plan_has_enough_free_text(_json.dumps(DEFAULT_GERMAN_QUESTION_PLAN))
