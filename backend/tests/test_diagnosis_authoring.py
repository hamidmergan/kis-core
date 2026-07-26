"""Expert-authored diagnosis questions: data model, modes and deterministic grading.

The diagnosis moves from "one LLM call per question" to expert-authored items.
An option question carries its own options with a correct/incorrect flag, and is
graded in code (no model) by comparing the learner's picks to the correct set.
A free-text item carries the question text and an optional example answer; it is
still judged by the one final LLM call. A slot with neither is "auto" and the
model generates it as before.

These tests pin the parsing (backwards compatible with the old band/type/text
plans), the mode a slot resolves to, and the all-or-nothing grading.
"""

import json

import pytest

import random

from src.services.aia_diagnosis_chat import (
    DEFAULT_GERMAN_QUESTION_PLAN,
    OPTION_QUESTION_TYPES,
    QUESTION_PLAN,
    answered_items,
    auto_question_payload,
    build_grading_brief,
    correct_values,
    grade_selection,
    is_multi_correct,
    manual_question_payload,
    option_values,
    parse_auto_question,
    parse_question_plan,
    question_mode,
    question_plan_is_valid,
    resolve_question_plan,
    validate_auto_options,
    DiagnosisChatError,
)


# ─── Parsing: options + example, backwards compatible ──────────────────────

def test_parse_keeps_type_text_plans_working_and_strips_legacy_band():
    """The old shape (type, optional verbatim text) still parses; a legacy band is
    dropped, since questions no longer carry a level."""
    raw = json.dumps([
        {"band": "A1", "type": "gap fill"},
        {"band": "B2", "type": "free writing", "text": "Schreibe drei Sätze."},
    ])
    assert parse_question_plan(raw) == [
        {"type": "gap fill"},
        {"type": "free writing", "text": "Schreibe drei Sätze."},
    ]


def test_parse_accepts_options_with_correct_flags():
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
    assert step["text"] == "Ich ___ jeden Tag zur Arbeit."
    assert step["options"] == [
        {"text": "gehe", "correct": True},
        {"text": "gehst", "correct": False},
        {"text": "geht", "correct": False},
        {"text": "gehen", "correct": False},
    ]


def test_parse_accepts_multiple_correct_options():
    raw = json.dumps([{
        "band": "A1", "type": "multiple choice", "text": "Was passt?",
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
        "band": "A1", "type": "gap fill", "text": "Q",
        "options": [{"text": "a", "correct": False}, {"text": "b", "correct": False}],
    }])
    assert parse_question_plan(raw) == QUESTION_PLAN


def test_parse_falls_back_on_option_with_empty_text():
    raw = json.dumps([{
        "band": "A1", "type": "gap fill", "text": "Q",
        "options": [{"text": "", "correct": True}, {"text": "b", "correct": False}],
    }])
    assert parse_question_plan(raw) == QUESTION_PLAN


def test_parse_falls_back_on_too_few_options():
    raw = json.dumps([{
        "band": "A1", "type": "gap fill", "text": "Q",
        "options": [{"text": "only", "correct": True}],
    }])
    assert parse_question_plan(raw) == QUESTION_PLAN


def test_parse_drops_options_on_free_text_types():
    """Options make no sense on error correction / free writing and are stripped,
    rather than nuking the plan, so a stray field from the editor is forgiving."""
    raw = json.dumps([{
        "band": "B2", "type": "free writing", "text": "Schreib was.",
        "options": [{"text": "x", "correct": True}, {"text": "y", "correct": False}],
    }])
    step = parse_question_plan(raw)[0]
    assert "options" not in step
    assert step["text"] == "Schreib was."


# ─── Question mode ─────────────────────────────────────────────────────────

def test_mode_manual_options_needs_text_and_options():
    step = {"band": "A1", "type": "gap fill", "text": "Q",
            "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}]}
    assert question_mode(step) == "manual_options"


def test_mode_manual_text_for_free_text_with_text():
    step = {"band": "A2", "type": "error correction", "text": "Verbessere: ..."}
    assert question_mode(step) == "manual_text"


def test_mode_auto_when_option_type_has_text_but_no_options():
    """Half-authored (question but no answer key) stays auto: the model fills it,
    so the expert is never forced to complete a row before the test works."""
    step = {"band": "A1", "type": "gap fill", "text": "Q"}
    assert question_mode(step) == "auto"


def test_mode_auto_for_bare_band_type():
    assert question_mode({"band": "A1", "type": "gap fill"}) == "auto"
    assert question_mode({"band": "B2", "type": "free writing"}) == "auto"


# ─── Deterministic grading (all-or-nothing) ────────────────────────────────

def _opt_step(*pairs):
    return {"band": "A1", "type": "multiple choice", "text": "Q",
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


# ─── Single-correct enforcement for AUTO (model-generated) options ─────────

def test_validate_auto_options_accepts_exactly_one_correct():
    opts = [{"text": "gehe", "correct": True},
            {"text": "gehst", "correct": False},
            {"text": "geht", "correct": False},
            {"text": "gehen", "correct": False}]
    assert validate_auto_options(opts) == opts


def test_validate_auto_options_rejects_two_correct():
    """The exact bug from the screenshot: 'ging' and 'gehe' both marked right."""
    opts = [{"text": "geht", "correct": False},
            {"text": "ging", "correct": True},
            {"text": "gehen", "correct": False},
            {"text": "gehe", "correct": True}]
    with pytest.raises(DiagnosisChatError):
        validate_auto_options(opts)


def test_validate_auto_options_rejects_zero_correct():
    opts = [{"text": "a", "correct": False}, {"text": "b", "correct": False}]
    with pytest.raises(DiagnosisChatError):
        validate_auto_options(opts)


def test_validate_auto_options_rejects_too_few():
    with pytest.raises(DiagnosisChatError):
        validate_auto_options([{"text": "only", "correct": True}])


# ─── Client payloads: never leak the answer key ────────────────────────────

def test_manual_option_payload_hides_correct_flags_and_shuffles():
    step = {"band": "A1", "type": "gap fill", "text": "Ich ___ Student.",
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


def test_manual_option_payload_marks_multi():
    step = {"band": "A1", "type": "multiple choice", "text": "Q",
            "options": [{"text": "a", "correct": True},
                        {"text": "b", "correct": True},
                        {"text": "c", "correct": False}]}
    assert manual_question_payload(step)["multi"] is True


def test_manual_free_text_payload_has_no_options():
    step = {"band": "B2", "type": "free writing", "text": "Schreib drei Sätze."}
    payload = manual_question_payload(step)
    assert payload == {"done": False, "message": "Schreib drei Sätze."}


def test_auto_payload_strips_flags_and_is_single():
    parsed = parse_auto_question(
        '{"done": false, "message": "Ich ___ Student.", "options": ['
        '{"text": "bin", "correct": true}, {"text": "ist", "correct": false},'
        '{"text": "sind", "correct": false}, {"text": "seid", "correct": false}]}',
        want_options=True,
    )
    payload = auto_question_payload(parsed, rng=random.Random(2))
    assert payload["multi"] is False
    assert sorted(payload["options"]) == ["bin", "ist", "seid", "sind"]
    assert "correct" not in str(payload)


def test_parse_auto_question_free_text_needs_no_options():
    parsed = parse_auto_question(
        '{"done": false, "message": "Schreib drei Sätze über deinen Tag."}',
        want_options=False,
    )
    assert parsed == {"message": "Schreib drei Sätze über deinen Tag."}


def test_parse_auto_question_rejects_two_correct():
    raw = ('{"done": false, "message": "Ich ___ zur Arbeit.", "options": ['
           '{"text": "gehe", "correct": true}, {"text": "ging", "correct": true},'
           '{"text": "geht", "correct": false}, {"text": "gehen", "correct": false}]}')
    with pytest.raises(DiagnosisChatError):
        parse_auto_question(raw, want_options=True)


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
    plan = [{"band": "A1", "type": "gap fill", "text": "Ich ___ Student.",
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
    plan = [{"band": "A1", "type": "gap fill", "text": "Q",
             "options": [{"text": "bin", "correct": True},
                         {"text": "ist", "correct": False}]}]
    history = [
        {"role": "assistant", "content": "Q", "options": ["ist", "bin"]},
        {"role": "user", "content": "ist", "selected": ["ist"]},
    ]
    assert "INCORRECT" in build_grading_brief(plan, history)


def test_grading_brief_defers_free_worded_pick_to_the_model():
    plan = [{"band": "A1", "type": "gap fill", "text": "Q",
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
    plan = [{"type": "error correction", "text": "Verbessere: Ich habe gegangen."}]
    history = [
        {"role": "assistant", "content": "Verbessere: Ich habe gegangen."},
        {"role": "user", "content": "Ich bin gegangen."},
    ]
    brief = build_grading_brief(plan, history)
    assert "A good answer looks like" not in brief
    assert "Judge the answer for its language level" in brief
    assert "Ich bin gegangen." in brief


# ─── Language-aware default resolution ─────────────────────────────────────

def test_resolve_uses_german_authored_set_for_german_with_no_config():
    assert resolve_question_plan("", "de") is DEFAULT_GERMAN_QUESTION_PLAN
    assert resolve_question_plan("   ", "de") is DEFAULT_GERMAN_QUESTION_PLAN


def test_resolve_uses_language_agnostic_default_for_other_languages():
    """Any non-German diagnosis with no config falls back to the model-generated
    plan, so a fresh install in any language still works out of the box."""
    assert resolve_question_plan("", "en") is QUESTION_PLAN
    assert resolve_question_plan("", "uk") is QUESTION_PLAN
    assert resolve_question_plan("", None) is QUESTION_PLAN


def test_resolve_prefers_a_stored_admin_plan_over_the_defaults():
    import json as _json
    stored = _json.dumps([{"type": "free writing", "text": "Schreib was."}])
    plan = resolve_question_plan(stored, "de")
    assert plan == [{"type": "free writing", "text": "Schreib was."}]


# ─── Save-path validation ──────────────────────────────────────────────────

def test_plan_is_valid_accepts_old_and_new_shapes():
    import json as _json
    assert question_plan_is_valid(_json.dumps([{"band": "A1", "type": "gap fill"}]))
    assert question_plan_is_valid(_json.dumps([{
        "band": "A1", "type": "gap fill", "text": "Q",
        "options": [{"text": "a", "correct": True}, {"text": "b", "correct": False}],
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


# ─── The shipped German set is well-formed and fully authored ──────────────

def test_german_default_matches_the_type_sequence():
    assert [s["type"] for s in DEFAULT_GERMAN_QUESTION_PLAN] == \
        [s["type"] for s in QUESTION_PLAN]
    # No question carries a band any more: level is read from the answers.
    assert all("band" not in s for s in DEFAULT_GERMAN_QUESTION_PLAN)


def test_german_default_has_no_auto_slots():
    """Every slot is fully authored, so a German diagnosis spends zero calls on
    questions: option slots are manual_options, free-text slots manual_text."""
    for step in DEFAULT_GERMAN_QUESTION_PLAN:
        if step["type"] in OPTION_QUESTION_TYPES:
            assert question_mode(step) == "manual_options"
        else:
            assert question_mode(step) == "manual_text"


def test_german_default_option_slots_are_single_correct():
    for step in DEFAULT_GERMAN_QUESTION_PLAN:
        if step["type"] in OPTION_QUESTION_TYPES:
            assert len(correct_values(step)) == 1, step["text"]


def test_german_default_round_trips_through_parse_and_validation():
    import json as _json
    raw = _json.dumps(DEFAULT_GERMAN_QUESTION_PLAN)
    assert question_plan_is_valid(raw)
    assert parse_question_plan(raw) == DEFAULT_GERMAN_QUESTION_PLAN


# ─── Free-text minimum (save-path policy, separate from structural validity) ─

def test_count_free_text_questions():
    from src.services.aia_diagnosis_chat import count_free_text_questions
    plan = [
        {"band": "A1", "type": "gap fill"},
        {"band": "A2", "type": "error correction"},
        {"band": "B2", "type": "free writing"},
    ]
    assert count_free_text_questions(plan) == 2
    assert count_free_text_questions([{"band": "A1", "type": "multiple choice"}]) == 0


def test_plan_needs_at_least_two_free_text():
    import json as _json
    from src.services.aia_diagnosis_chat import question_plan_has_enough_free_text
    too_few = _json.dumps([
        {"band": "A1", "type": "gap fill"},
        {"band": "A2", "type": "multiple choice"},
        {"band": "B2", "type": "error correction"},
    ])
    enough = _json.dumps([
        {"band": "A2", "type": "error correction"},
        {"band": "B2", "type": "free writing"},
    ])
    assert not question_plan_has_enough_free_text(too_few)
    assert question_plan_has_enough_free_text(enough)


def test_plan_free_text_check_is_robust_to_muck():
    from src.services.aia_diagnosis_chat import question_plan_has_enough_free_text
    assert not question_plan_has_enough_free_text("{not json")
    assert not question_plan_has_enough_free_text('{"not": "a list"}')


def test_shipped_plans_meet_the_free_text_minimum():
    """Regression: a default must never dip below the enforced floor, or a fresh
    install would ship a plan the save path would then reject."""
    import json as _json
    from src.services.aia_diagnosis_chat import (
        question_plan_has_enough_free_text, QUESTION_PLAN, DEFAULT_GERMAN_QUESTION_PLAN,
    )
    assert question_plan_has_enough_free_text(_json.dumps(QUESTION_PLAN))
    assert question_plan_has_enough_free_text(_json.dumps(DEFAULT_GERMAN_QUESTION_PLAN))
