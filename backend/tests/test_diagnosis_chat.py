"""Language diagnosis chat: prompt rendering and turn-response validation.

The diagnosis is a short adaptive interview. Per turn the model answers with a
JSON object that either carries the next question or the final CEFR verdict, so
the parser has to accept exactly those two shapes and reject everything else -
a half-filled verdict must never reach ``set_user_language_level``.
"""

import json

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
    """B1+ is the top outcome; the prompt must not offer B2/C1/C2 as verdicts."""
    fmt = DEFAULT_DIAGNOSIS_PROMPT[DEFAULT_DIAGNOSIS_PROMPT.find("LEVEL ANCHORS"):]
    assert "B1+" in fmt
    for gone in ("C1:", "C2:"):
        assert gone not in fmt


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
    assert next_question_message(1) in messages[2]["content"]


def test_history_is_passed_through_with_a_question_hint_appended():
    history = _history(1)
    messages = build_turn_messages("SYS", history)
    # System prompt, the untouched transcript, then the hint for question 2.
    assert messages[: 1 + len(history)] == [{"role": "system", "content": "SYS"}, *history]
    assert messages[-1] == {"role": "system", "content": next_question_message(2)}


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
    text = keep_going_message(2)
    assert "2" in text and str(QUESTION_COUNT) in text
    assert "done=false" in text
