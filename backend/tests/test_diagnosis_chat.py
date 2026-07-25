"""Language diagnosis chat: prompt rendering and turn-response validation.

The diagnosis is a short adaptive interview. Per turn the model answers with a
JSON object that either carries the next question or the final CEFR verdict, so
the parser has to accept exactly those two shapes and reject everything else -
a half-filled verdict must never reach ``set_user_language_level``.
"""

import json
import re

import pytest

from src.features.ai_assistant.routes.language_training.diagnosis import (
    _rejects_json_mode,
    build_turn_messages,
    running_turn_payload,
)
from src.services.aia_diagnosis_chat import (
    DEFAULT_DIAGNOSIS_PROMPT,
    FORCE_FINISH_MESSAGE,
    KICKOFF_MESSAGE,
    QUESTION_BANDS,
    QUESTION_COUNT,
    QUESTION_PLAN,
    PROMPT_PLACEHOLDER,
    REQUIRED_SKILLS,
    DiagnosisChatError,
    keep_going_message,
    next_question_message,
    parse_question_plan,
    parse_turn_response,
    render_system_prompt,
)


# ─── Rendering ─────────────────────────────────────────────────────────────

def test_render_replaces_every_placeholder_occurrence():
    template = f"Speak {PROMPT_PLACEHOLDER}. Only {PROMPT_PLACEHOLDER}, nothing else."
    assert render_system_prompt(template, "French") == (
        "Speak French. Only French, nothing else."
    )


def test_render_keeps_json_braces_intact():
    """The template carries a JSON example, so str.format would explode on it."""
    template = 'Answer with {"done": false, "message": "<in ' + PROMPT_PLACEHOLDER + '>"}'
    rendered = render_system_prompt(template, "Italian")
    assert '{"done": false' in rendered
    assert "Italian" in rendered


def test_render_leaves_template_without_placeholder_alone():
    assert render_system_prompt("no variable here", "Turkish") == "no variable here"


def test_default_prompt_is_usable_out_of_the_box():
    """No configuration at all must still produce a working system prompt."""
    assert PROMPT_PLACEHOLDER in DEFAULT_DIAGNOSIS_PROMPT
    rendered = render_system_prompt(DEFAULT_DIAGNOSIS_PROMPT, "Spanish")
    assert PROMPT_PLACEHOLDER not in rendered
    assert "Spanish" in rendered
    # Language-agnostic by design: no German wordlists or grammar terms baked in.
    assert "German" not in DEFAULT_DIAGNOSIS_PROMPT
    # The register rule must stay language-neutral too: naming du/Sie or tu/vous
    # would silently make the prompt German- or French-only.
    for tv_pair in ("du", "Sie", "tu", "vous", "usted"):
        assert f" {tv_pair} " not in DEFAULT_DIAGNOSIS_PROMPT
    assert "informal second person" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_defines_all_six_task_types():
    """The six types are the backbone of the test, one per question."""
    for task_type in ("gap fill", "multiple choice", "error correction",
                      "reading comprehension", "free writing", "situation"):
        assert task_type in DEFAULT_DIAGNOSIS_PROMPT
    # The type is dictated per question, not chosen by the model.
    assert "THE TASK TYPES, fixed per question" in DEFAULT_DIAGNOSIS_PROMPT
    # Letter answers only work if the learner is told they may reply with one.
    assert "a), b), c), d)" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_lays_the_task_out_over_lines():
    """One long line is unreadable for the learners this is built for: the
    instruction, the sentence and every option need their own line."""
    assert "TASK LAYOUT" in DEFAULT_DIAGNOSIS_PROMPT
    assert "ONE PER LINE" in DEFAULT_DIAGNOSIS_PROMPT
    # The layout is worthless if the model packs it into a single JSON line.
    assert "\\n" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_demands_a_single_defensible_answer():
    """Options that all fit ("I bought a book / a car / a house") grade nothing."""
    assert "EXACTLY ONE option is correct" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_builds_items_like_a_placement_test():
    """Modelled on published placement tests (Klett Netzwerk A1-B1, ISS Aarau
    A1-B2): options are minimal pairs of one form, never different content."""
    assert "ITEM DESIGN" in DEFAULT_DIAGNOSIS_PROMPT
    assert "SAME class as the correct one" in DEFAULT_DIAGNOSIS_PROMPT
    # A reading item whose answer is copied out of the text grades nothing.
    assert "paraphrase" in DEFAULT_DIAGNOSIS_PROMPT


def test_difficulty_ladder_stays_language_agnostic():
    """The ladder names categories, so it survives a workspace set to any
    language; naming a concrete rule would silently make it German-only."""
    ladder = DEFAULT_DIAGNOSIS_PROMPT[DEFAULT_DIAGNOSIS_PROMPT.find("DIFFICULTY LADDER"):]
    assert "DIFFICULTY LADDER" in DEFAULT_DIAGNOSIS_PROMPT
    for band in ("A1 (questions 1-2)", "A2 (questions 3-4)",
                 "B1 (questions 5-6)", "B2 (questions 7-8)"):
        assert band in ladder
    assert PROMPT_PLACEHOLDER in ladder


def test_default_prompt_is_a_fixed_staircase_not_adaptive():
    """The whole point of the redesign: fixed length, fixed difficulty per slot."""
    assert "FIXED STAIRCASE" in DEFAULT_DIAGNOSIS_PROMPT
    assert "exactly 8 questions" in DEFAULT_DIAGNOSIS_PROMPT
    assert "fixed staircase, not adaptive" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_uses_only_the_four_outcomes():
    """B1+ is the top outcome; the grading rules must not offer C1/C2 as verdicts."""
    from src.services.aia_diagnosis_chat import DEFAULT_GRADING_RULES
    assert "B1+" in DEFAULT_GRADING_RULES
    for gone in ("C1:", "C2:"):
        assert gone not in DEFAULT_GRADING_RULES
    # And the OUTPUT FORMAT still constrains the verdict to the four outcomes.
    assert '"A1", "A2", "B1", "B1+"' in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_forbids_bracketed_hints():
    """A blank annotated with the word class hands the answer to the learner."""
    assert "NO HINTS IN BRACKETS" in DEFAULT_DIAGNOSIS_PROMPT
    assert "___" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_makes_it_conversational():
    """The model must react to the answer before moving on, like a person would."""
    assert "short, warm reaction" in DEFAULT_DIAGNOSIS_PROMPT
    # The interface already greets, so a second greeting would read as a stutter.
    assert "Do NOT greet the learner" in DEFAULT_DIAGNOSIS_PROMPT
    for level in ("A1", "A2", "B1", "B1+"):
        assert level in DEFAULT_DIAGNOSIS_PROMPT
    for skill in REQUIRED_SKILLS:
        assert skill in DEFAULT_DIAGNOSIS_PROMPT


# ─── Parsing: interview continues ──────────────────────────────────────────

def test_parse_ongoing_turn():
    raw = json.dumps({"done": False, "message": "Comment vas-tu?"})
    assert parse_turn_response(raw) == {"done": False, "message": "Comment vas-tu?"}


def test_parse_strips_markdown_fence():
    raw = '```json\n{"done": false, "message": "Wie geht es dir?"}\n```'
    assert parse_turn_response(raw)["message"] == "Wie geht es dir?"


def test_parse_ongoing_turn_keeps_the_reaction():
    """The reaction is its own chat bubble, so it must survive as its own field."""
    raw = json.dumps({"done": False, "reaction": "Gut erzählt!", "message": "Ergänze: Ich habe dort ___."})
    assert parse_turn_response(raw) == {
        "done": False,
        "message": "Ergänze: Ich habe dort ___.",
        "reaction": "Gut erzählt!",
    }


@pytest.mark.parametrize("reaction", ["", "   ", None, 42])
def test_parse_ongoing_turn_drops_unusable_reaction(reaction):
    """First turn has nothing to react to; an empty bubble must not be rendered."""
    raw = json.dumps({"done": False, "reaction": reaction, "message": "Wie geht es dir?"})
    assert parse_turn_response(raw) == {"done": False, "message": "Wie geht es dir?"}


def test_parse_final_turn_ignores_reaction():
    """The verdict is shown on the result screen, which has no bubble for it."""
    result = parse_turn_response(_final(reaction="Stark!"))
    assert "reaction" not in result


def test_default_prompt_asks_for_a_separate_reaction_field():
    assert '"reaction"' in DEFAULT_DIAGNOSIS_PROMPT
    assert "two chat bubbles" in DEFAULT_DIAGNOSIS_PROMPT


def test_parse_ongoing_turn_drops_stray_level():
    """A level only counts on the final turn; an early one must not be persisted."""
    raw = json.dumps({"done": False, "message": "Weiter?", "level": "C2"})
    assert parse_turn_response(raw) == {"done": False, "message": "Weiter?"}


# ─── Parsing: final verdict ────────────────────────────────────────────────

def _final(**overrides) -> str:
    payload = {
        "done": True,
        "message": "Gut gemacht.",
        "level": "B1",
        "skill_scores": {s: 60 for s in REQUIRED_SKILLS},
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_parse_final_turn():
    result = parse_turn_response(_final())
    assert result["done"] is True
    assert result["level"] == "B1"
    assert result["message"] == "Gut gemacht."
    assert result["skill_scores"] == {s: 60 for s in REQUIRED_SKILLS}


def test_parse_final_turn_coerces_float_scores_to_int():
    result = parse_turn_response(_final(skill_scores={s: 72.6 for s in REQUIRED_SKILLS}))
    assert all(isinstance(v, int) for v in result["skill_scores"].values())


def test_parse_final_turn_ignores_extra_skills():
    scores = {s: 50 for s in REQUIRED_SKILLS}
    scores["listening"] = 90
    result = parse_turn_response(_final(skill_scores=scores))
    assert set(result["skill_scores"]) == REQUIRED_SKILLS


# ─── Parsing: rejection ────────────────────────────────────────────────────

def test_parse_recovers_json_wrapped_in_prose():
    """Seen live: the model prepends a sentence before the object."""
    raw = 'Sure, here is the next question:\n{"done": false, "message": "Wie geht es dir?"}\nHope that helps!'
    assert parse_turn_response(raw) == {"done": False, "message": "Wie geht es dir?"}


def test_parse_recovers_final_verdict_wrapped_in_prose():
    raw = "Here is my assessment:\n" + _final() + "\nLet me know if you need more."
    result = parse_turn_response(raw)
    assert result["done"] is True and result["level"] == "B1"


def test_parse_recovers_json_after_a_reasoning_block():
    raw = '<think>The learner made two case errors.</think>{"done": false, "message": "Weiter?"}'
    assert parse_turn_response(raw)["message"] == "Weiter?"


def test_parse_rejects_non_json():
    with pytest.raises(DiagnosisChatError):
        parse_turn_response("Sure! Here is your next question.")


def test_parse_rejects_broken_json_object():
    with pytest.raises(DiagnosisChatError):
        parse_turn_response('Here you go: {"done": false, "message": }')


def test_parse_rejects_empty_message():
    with pytest.raises(DiagnosisChatError):
        parse_turn_response(json.dumps({"done": False, "message": "   "}))


def test_parse_accepts_b1_plus_as_the_top_outcome():
    assert parse_turn_response(_final(level="B1+"))["level"] == "B1+"


@pytest.mark.parametrize("level", ["B2", "C1", "C2", "B3", "A0"])
def test_parse_rejects_levels_outside_the_four_outcomes(level):
    """The set shrank to A1/A2/B1/B1+, so the old CEFR bands must now be refused."""
    with pytest.raises(DiagnosisChatError):
        parse_turn_response(_final(level=level))


def test_parse_rejects_missing_skill():
    scores = {s: 50 for s in REQUIRED_SKILLS}
    scores.pop("pragmatics")
    with pytest.raises(DiagnosisChatError):
        parse_turn_response(_final(skill_scores=scores))


def test_parse_rejects_score_out_of_range():
    with pytest.raises(DiagnosisChatError):
        parse_turn_response(_final(skill_scores={**{s: 50 for s in REQUIRED_SKILLS},
                                                  "writing": 140}))


def test_parse_rejects_non_numeric_score():
    with pytest.raises(DiagnosisChatError):
        parse_turn_response(_final(skill_scores={**{s: 50 for s in REQUIRED_SKILLS},
                                                  "grammar": "good"}))


def test_parse_rejects_final_turn_without_scores():
    payload = json.loads(_final())
    del payload["skill_scores"]
    with pytest.raises(DiagnosisChatError):
        parse_turn_response(json.dumps(payload))


# ─── Turn assembly ─────────────────────────────────────────────────────────

def _history(answers: int) -> list[dict]:
    """A transcript with `answers` completed question/answer pairs."""
    history = []
    for i in range(answers):
        history.append({"role": "assistant", "content": f"Frage {i}"})
        history.append({"role": "user", "content": f"Antwort {i}"})
    return history


def test_empty_history_gets_a_kickoff_then_the_first_question_hint():
    """Without the kickoff the model sees only system turns and may stay silent;
    the band hint that follows pins question 1 to the bottom of the ladder."""
    messages = build_turn_messages("SYS", [])
    assert [m["role"] for m in messages] == ["system", "user", "system"]
    assert messages[1]["content"] == KICKOFF_MESSAGE
    # Question 1's hint sits in the trailing system turn. The correct-option
    # position is randomised, so match the stable band/type parts, not the letter.
    assert "question 1 of" in messages[2]["content"]
    assert "gap fill" in messages[2]["content"]


def test_history_is_passed_through_with_a_question_hint_appended():
    history = _history(1)
    messages = build_turn_messages("SYS", history)
    # System prompt, the untouched transcript, then the hint for question 2.
    assert messages[: 1 + len(history)] == [{"role": "system", "content": "SYS"}, *history]
    # The trailing turn is the system hint for question 2. Its correct-option
    # position is randomised, so assert the role and the stable "question 2" part.
    assert messages[-1]["role"] == "system"
    assert "question 2 of" in messages[-1]["content"]


def test_last_question_still_gets_a_hint_not_a_verdict():
    """After 7 answers we still owe question 8, so the turn must ask, not force."""
    messages = build_turn_messages("SYS", _history(QUESTION_COUNT - 1))
    assert messages[-1]["content"] == next_question_message(QUESTION_COUNT)
    assert FORCE_FINISH_MESSAGE not in messages[-1]["content"]


def test_verdict_is_forced_only_after_the_last_answer():
    messages = build_turn_messages("SYS", _history(QUESTION_COUNT))
    assert messages[-1] == {"role": "system", "content": FORCE_FINISH_MESSAGE}
    # And no stray question hint sneaks in on the verdict turn.
    assert not any("Now ask question" in m["content"]
                   for m in messages if m["role"] == "system")


def test_each_question_hint_names_its_band_and_type():
    """The staircase couples both to the slot: Q1 gap fill/A1 up to Q8 free/B2."""
    expected = {
        1: ("gap fill", "A1"),
        3: ("error correction", "A2"),
        6: ("situation", "B1"),
        8: ("free writing", "B2"),
    }
    for number, (task_type, band) in expected.items():
        hint = next_question_message(number)
        assert f"question {number} of {QUESTION_COUNT}" in hint
        assert task_type in hint
        assert band in hint


def test_plan_is_eight_rising_steps_two_per_band():
    assert QUESTION_COUNT == 8
    assert QUESTION_BANDS == ["A1", "A1", "A2", "A2", "B1", "B1", "B2", "B2"]
    types = [step["type"] for step in QUESTION_PLAN]
    # All six task types appear...
    assert set(types) == {"gap fill", "multiple choice", "error correction",
                          "reading comprehension", "situation", "free writing"}
    # ...and multiple choice fills the two extra quiz slots, so it runs three times.
    assert types.count("multiple choice") == 3
    # The ladder never steps down.
    order = ["A1", "A2", "B1", "B2"]
    ranks = [order.index(b) for b in QUESTION_BANDS]
    assert ranks == sorted(ranks)


# ─── Response shape ────────────────────────────────────────────────────────

def test_running_turn_payload_forwards_the_reaction():
    """Regression: the route used to rebuild the response from message alone,
    which silently swallowed the reaction the model had produced."""
    payload = running_turn_payload(
        {"done": False, "message": "Fülle die Lücke: ___", "reaction": "Gut erzählt!"}
    )
    assert payload == {
        "done": False,
        "message": "Fülle die Lücke: ___",
        "reaction": "Gut erzählt!",
    }


def test_running_turn_payload_omits_absent_reaction():
    payload = running_turn_payload({"done": False, "message": "Erste Frage?"})
    assert payload == {"done": False, "message": "Erste Frage?"}


def test_running_turn_payload_drops_an_early_level():
    payload = running_turn_payload({"done": False, "message": "Weiter?", "level": "C2"})
    assert "level" not in payload


# ─── JSON mode fallback ────────────────────────────────────────────────────

class _ProviderError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def test_rate_limit_does_not_disable_json_mode():
    """A 429 is load, not a capability signal. Disabling on it would give up
    JSON mode permanently the first time the shared limit is hit."""
    assert not _rejects_json_mode(_ProviderError("Failed to process request", 429))


def test_unrelated_400_does_not_disable_json_mode():
    assert not _rejects_json_mode(_ProviderError("context length exceeded", 400))


def test_response_format_rejection_disables_json_mode():
    assert _rejects_json_mode(
        _ProviderError("Unsupported parameter: 'response_format'", 400)
    )
    assert _rejects_json_mode(_ProviderError("json_object is not supported", 400))


def test_error_without_status_does_not_disable_json_mode():
    assert not _rejects_json_mode(_ProviderError("connection reset"))


def test_question_count_is_eight():
    assert QUESTION_COUNT == 8


def test_keep_going_message_names_both_numbers():
    """The nudge has to be concrete or the model repeats the same verdict."""
    text = keep_going_message(2, QUESTION_COUNT)
    assert "2" in text and str(QUESTION_COUNT) in text
    assert "done=false" in text


def test_keep_going_message_takes_total():
    assert "of 6" in keep_going_message(3, 6)


# ─── Admin-configurable question plan ──────────────────────────────────────

def test_parse_question_plan_empty_returns_default():
    assert parse_question_plan("") == QUESTION_PLAN
    assert parse_question_plan("   ") == QUESTION_PLAN


def test_parse_question_plan_invalid_json_returns_default():
    assert parse_question_plan("{not json") == QUESTION_PLAN


def test_parse_question_plan_rejects_bad_band_or_type():
    bad_band = json.dumps([{"band": "C1", "type": "gap fill"}])
    bad_type = json.dumps([{"band": "A1", "type": "essay"}])
    assert parse_question_plan(bad_band) == QUESTION_PLAN
    assert parse_question_plan(bad_type) == QUESTION_PLAN


def test_parse_question_plan_accepts_valid_plan_with_optional_text():
    raw = json.dumps([
        {"band": "A1", "type": "gap fill"},
        {"band": "B2", "type": "free writing", "text": "Schreibe drei Sätze über deinen Tag."},
    ])
    assert parse_question_plan(raw) == [
        {"band": "A1", "type": "gap fill"},
        {"band": "B2", "type": "free writing", "text": "Schreibe drei Sätze über deinen Tag."},
    ]


def test_next_question_message_uses_verbatim_text_when_present():
    plan = [{"band": "A1", "type": "gap fill", "text": "Fülle die Lücke: Ich ___ Student."}]
    msg = next_question_message(1, plan)
    assert "Ich ___ Student." in msg
    assert "1 of 1" in msg


def test_next_question_message_uses_type_and_band_without_text():
    plan = [{"band": "A2", "type": "error correction"}]
    msg = next_question_message(1, plan)
    assert "error correction" in msg
    assert "A2" in msg


def test_correct_option_letter_is_a_valid_position_or_none():
    """Option-bearing questions get one of a, b, c, d; the two free-text slots
    (error correction, free writing) get None."""
    from src.services.aia_diagnosis_chat import (
        correct_option_letter,
        CORRECT_OPTION_POSITIONS,
    )
    # Default plan option questions in order: Q1, Q2, Q4, Q5, Q6, Q7.
    for number in (1, 2, 4, 5, 6, 7):
        assert correct_option_letter(number, QUESTION_PLAN) in CORRECT_OPTION_POSITIONS
    assert correct_option_letter(3, QUESTION_PLAN) is None  # error correction
    assert correct_option_letter(8, QUESTION_PLAN) is None  # free writing


def test_correct_option_letter_is_random_not_a_fixed_pattern():
    """Regression for the predictable-pattern fix: the position must not settle
    onto one letter or a learnable rotation. Over many draws for the same slot,
    every position shows up."""
    from src.services.aia_diagnosis_chat import (
        correct_option_letter,
        CORRECT_OPTION_POSITIONS,
    )
    seen = {correct_option_letter(1, QUESTION_PLAN) for _ in range(200)}
    assert seen == set(CORRECT_OPTION_POSITIONS)


def test_next_question_message_dictates_a_correct_position_for_option_types():
    msg = next_question_message(2, QUESTION_PLAN)  # multiple choice -> some position
    assert re.search(r"position [abcd]\)", msg)


def test_next_question_message_has_no_position_for_optionless_types():
    msg = next_question_message(3, QUESTION_PLAN)  # error correction -> no options
    assert "CORRECT option at position" not in msg


# ─── Grading rules + calibration examples ──────────────────────────────────

def test_parse_level_examples_empty_returns_defaults():
    from src.services.aia_diagnosis_chat import parse_level_examples, DEFAULT_LEVEL_EXAMPLES
    assert parse_level_examples("") == DEFAULT_LEVEL_EXAMPLES
    assert parse_level_examples("   ") == DEFAULT_LEVEL_EXAMPLES


def test_parse_level_examples_merges_partial_override_onto_defaults():
    from src.services.aia_diagnosis_chat import parse_level_examples, DEFAULT_LEVEL_EXAMPLES
    out = parse_level_examples(json.dumps({"A2": "Mein eigenes A2 Beispiel."}))
    assert out["A2"] == "Mein eigenes A2 Beispiel."
    # The other three stay at the shipped default.
    assert out["A1"] == DEFAULT_LEVEL_EXAMPLES["A1"]
    assert out["B1"] == DEFAULT_LEVEL_EXAMPLES["B1"]
    assert out["B2"] == DEFAULT_LEVEL_EXAMPLES["B2"]


def test_parse_level_examples_ignores_unknown_keys_and_bad_json():
    from src.services.aia_diagnosis_chat import parse_level_examples, DEFAULT_LEVEL_EXAMPLES
    assert parse_level_examples("{oops") == DEFAULT_LEVEL_EXAMPLES
    out = parse_level_examples(json.dumps({"C1": "nope", "A1": "Ja."}))
    assert "C1" not in out
    assert out["A1"] == "Ja."


def test_build_examples_block_lists_all_four_examples():
    from src.services.aia_diagnosis_chat import build_examples_block, DEFAULT_LEVEL_EXAMPLES
    block = build_examples_block(DEFAULT_LEVEL_EXAMPLES)
    for level in ("A1", "A2", "B1", "B2"):
        assert f"- {level}:" in block
    # The default ships two examples per band, rendered as sub-items.
    assert "Am Samstag gehe ich ins Kino." in block
    assert "Ich arbeite in einem Büro." in block
    # The explaining text is NOT here: it lives visibly in the prompt template.
    assert "CALIBRATION EXAMPLES" not in block


def test_build_examples_block_single_example_renders_inline():
    from src.services.aia_diagnosis_chat import build_examples_block
    block = build_examples_block({"A1": "Nur ein Satz."})
    assert "- A1: Nur ein Satz." in block


def test_build_examples_block_multiple_examples_render_as_subitems():
    from src.services.aia_diagnosis_chat import build_examples_block
    block = build_examples_block({"A1": "Satz eins.\nSatz zwei."})
    assert "- A1:" in block
    assert "  - Satz eins." in block
    assert "  - Satz zwei." in block


def test_build_examples_block_splits_on_double_dash():
    """Examples may be separated by '--', including as a leading marker per line."""
    from src.services.aia_diagnosis_chat import build_examples_block
    block = build_examples_block({"A1": "-- Satz eins. -- Satz zwei."})
    assert "  - Satz eins." in block
    assert "  - Satz zwei." in block


def test_build_examples_block_keeps_single_hyphen_inside_a_word():
    """A single hyphen (E-Mail) must not split the example."""
    from src.services.aia_diagnosis_chat import build_examples_block
    block = build_examples_block({"A1": "Ich schreibe eine E-Mail."})
    assert "- A1: Ich schreibe eine E-Mail." in block


def test_example_items_splits_on_dash_and_newline_keeps_hyphen_word():
    from src.services.aia_diagnosis_chat import example_items
    assert example_items("-- Satz eins.\n-- Satz zwei.") == ["Satz eins.", "Satz zwei."]
    assert example_items("Eins. -- Zwei.") == ["Eins.", "Zwei."]
    assert example_items("Ich schreibe eine E-Mail.") == ["Ich schreibe eine E-Mail."]
    assert example_items("") == []


def test_assemble_system_prompt_fills_both_placeholders():
    from src.services.aia_diagnosis_chat import (
        assemble_system_prompt, DEFAULT_DIAGNOSIS_PROMPT, DEFAULT_GRADING_RULES,
        DEFAULT_LEVEL_EXAMPLES, GRADING_PLACEHOLDER, EXAMPLES_PLACEHOLDER,
    )
    out = assemble_system_prompt(
        DEFAULT_DIAGNOSIS_PROMPT, DEFAULT_GRADING_RULES, DEFAULT_LEVEL_EXAMPLES, "German"
    )
    # Both placeholders consumed, language substituted, both sections present.
    assert GRADING_PLACEHOLDER not in out
    assert EXAMPLES_PLACEHOLDER not in out
    assert "{language}" not in out
    assert "LEVEL ASSIGNMENT" in out
    assert "CALIBRATION EXAMPLES" in out
    # The actual example content landed where {examples} was.
    assert "Am Samstag gehe ich ins Kino." in out


def test_assemble_system_prompt_appends_when_placeholders_missing():
    from src.services.aia_diagnosis_chat import (
        assemble_system_prompt, DEFAULT_GRADING_RULES, DEFAULT_LEVEL_EXAMPLES,
    )
    out = assemble_system_prompt(
        "A custom prompt with no placeholders.", DEFAULT_GRADING_RULES,
        DEFAULT_LEVEL_EXAMPLES, "German",
    )
    assert "LEVEL ASSIGNMENT" in out
    assert "CALIBRATION EXAMPLES" in out
    assert "Am Samstag gehe ich ins Kino." in out


def test_default_prompt_carries_both_placeholders_once():
    from src.services.aia_diagnosis_chat import (
        DEFAULT_DIAGNOSIS_PROMPT, GRADING_PLACEHOLDER, EXAMPLES_PLACEHOLDER,
    )
    assert DEFAULT_DIAGNOSIS_PROMPT.count(GRADING_PLACEHOLDER) == 1
    assert DEFAULT_DIAGNOSIS_PROMPT.count(EXAMPLES_PLACEHOLDER) == 1
    # The anchors moved out, so the main prompt no longer defines them itself.
    assert "LEVEL ANCHORS" not in DEFAULT_DIAGNOSIS_PROMPT


def test_build_turn_messages_forces_finish_at_plan_length():
    plan = [{"band": "A1", "type": "gap fill"}, {"band": "A2", "type": "situation"}]
    history = [
        {"role": "assistant", "content": "Q1"}, {"role": "user", "content": "a"},
        {"role": "assistant", "content": "Q2"}, {"role": "user", "content": "b"},
    ]
    messages = build_turn_messages("SYS", history, plan)
    assert messages[-1]["content"] == FORCE_FINISH_MESSAGE


def test_build_turn_messages_injects_next_question_from_plan():
    plan = [{"band": "A1", "type": "gap fill"}, {"band": "A2", "type": "situation"}]
    messages = build_turn_messages("SYS", [], plan)
    assert "gap fill" in messages[-1]["content"]
    assert "1 of 2" in messages[-1]["content"]


def test_diagnosis_config_defaults(monkeypatch):
    import asyncio
    from src.features.ai_assistant.routes.language_training import diagnosis as route
    monkeypatch.setattr(route.db, "get_setting", lambda key, default="": default)
    out = asyncio.run(route.config(current_user={"user_id": 1}))
    assert out["question_count"] == QUESTION_COUNT
    assert out["answer_max_chars"] == 2000
