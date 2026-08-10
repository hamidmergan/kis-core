"""Language diagnosis: prompt rendering, question generation and verdict parsing.

Jede Frage kommt ausgeschrieben aus dem Plan und wird ohne Modellaufruf
ausgeliefert, Auswahl- und Tippantworten bewertet der Code. Nur der eine
Abschluss-Aufruf spricht mit dem Modell. Dieses Modul haelt den gemeinsamen Prompt,
die Nachrichten der Abschlussbewertung und den Verdikt-Parser fest. Datenmodell und
deterministische Bewertung liegen in test_diagnosis_authoring.
"""

import json
import re

import pytest

from src.features.ai_assistant.routes.language_training.diagnosis import (
    _rejects_json_mode,
)
from src.services.aia_diagnosis_chat import (
    DEFAULT_DIAGNOSIS_PROMPT,
    DEFAULT_GERMAN_QUESTION_PLAN,
    FINAL_INSTRUCTION,
    PROMPT_PLACEHOLDER,
    DiagnosisChatError,
    build_final_messages,
    count_judged_questions,
    parse_question_plan,
    parse_turn_response,
    render_system_prompt,
)

QUESTION_COUNT = len(DEFAULT_GERMAN_QUESTION_PLAN)


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


def test_default_prompt_defines_both_task_types():
    """Zwei Arten tragen den Test, und der Prompt muss dieselben zwei Namen
    benutzen wie der Plan, sonst beschreibt er eine Aufgabe, die es nicht gibt."""
    assert "choice" in DEFAULT_DIAGNOSIS_PROMPT
    assert "free text" in DEFAULT_DIAGNOSIS_PROMPT
    # Die alten sechs Namen kommen nicht wieder vor.
    for gone in ("gap fill", "reading comprehension", "free writing"):
        assert gone not in DEFAULT_DIAGNOSIS_PROMPT
    # The type is dictated per question, not chosen by the model.
    assert "THERE ARE TWO TASK TYPES" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_returns_options_as_structured_data_not_letters():
    """Options travel in an array so the interface can shuffle them; the old
    a), b), c), d) layout inside the message is gone."""
    assert '"options"' in DEFAULT_DIAGNOSIS_PROMPT
    assert '"correct": true' in DEFAULT_DIAGNOSIS_PROMPT
    # No letters and no in-message option layout survive.
    assert "a), b), c), d)" not in DEFAULT_DIAGNOSIS_PROMPT
    assert "reply with the letter" not in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_carries_no_reaction_machinery():
    """The reaction bubble was removed; the model must not produce one."""
    assert '"reaction"' not in DEFAULT_DIAGNOSIS_PROMPT
    assert "two chat bubbles" not in DEFAULT_DIAGNOSIS_PROMPT
    assert "Do NOT react" in DEFAULT_DIAGNOSIS_PROMPT
    # The interface already greets, so a second greeting would read as a stutter.
    assert "Do NOT greet the learner" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_lays_the_task_out_over_lines():
    """One long line is unreadable for the learners this is built for: the
    instruction and the sentence need their own lines, options go in the array."""
    assert "TASK LAYOUT" in DEFAULT_DIAGNOSIS_PROMPT
    # The layout is worthless if the model packs it into a single JSON line.
    assert "\\n" in DEFAULT_DIAGNOSIS_PROMPT
    assert 'options in the "options" array'.split()[0] in DEFAULT_DIAGNOSIS_PROMPT


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


def test_difficulty_range_stays_language_agnostic():
    """The difficulty range names categories, so it survives a workspace set to
    any language; naming a concrete rule would silently make it German-only."""
    section = DEFAULT_DIAGNOSIS_PROMPT[DEFAULT_DIAGNOSIS_PROMPT.find("DIFFICULTY RANGE"):]
    assert "DIFFICULTY RANGE" in DEFAULT_DIAGNOSIS_PROMPT
    for level in ("A1:", "A2:", "B1:", "B2:", "C1:", "C2:"):
        assert level in section
    assert PROMPT_PLACEHOLDER in section


def test_default_prompt_is_a_fixed_set_not_adaptive():
    """Fixed length and task types, difficulty rising by position, not adapting to
    the answers."""
    assert "RISES FROM EASY TO HARD" in DEFAULT_DIAGNOSIS_PROMPT
    assert "fixed set of questions" in DEFAULT_DIAGNOSIS_PROMPT
    assert "not adaptive testing" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_places_from_the_learners_answers_not_a_question_label():
    """The redesign: questions carry no CEFR level, the model reads the answers."""
    assert "carry no level of their own" in DEFAULT_DIAGNOSIS_PROMPT
    assert "carry NO CEFR level" in DEFAULT_DIAGNOSIS_PROMPT
    assert "CALIBRATION EXAMPLES" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_uses_the_full_cefr_ladder():
    """The scale runs A1..C2; the level ladder and output format must offer all
    six, and the old collapsed 'B1+' outcome must be gone everywhere."""
    from src.services.aia_diagnosis_chat import DEFAULT_GRADING_RULES
    from src.services.aia_level_ladder import DEFAULT_LEVEL_DESCRIPTIONS
    assert "B1+" not in DEFAULT_GRADING_RULES
    for level in ("C1", "C2"):
        assert DEFAULT_LEVEL_DESCRIPTIONS[level].strip()
    # The OUTPUT FORMAT constrains the verdict to the six CEFR levels.
    assert '"A1", "A2", "B1", "B2", "C1", "C2"' in DEFAULT_DIAGNOSIS_PROMPT
    assert "B1+" not in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_forbids_bracketed_hints():
    """A blank annotated with the word class hands the answer to the learner."""
    assert "NO HINTS IN BRACKETS" in DEFAULT_DIAGNOSIS_PROMPT
    assert "___" in DEFAULT_DIAGNOSIS_PROMPT


def test_default_prompt_names_the_outcomes():
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        assert level in DEFAULT_DIAGNOSIS_PROMPT


def test_the_model_is_never_asked_for_per_skill_scores():
    """Prompt and both control messages must agree: level and message, no scores."""
    from src.services.aia_diagnosis_chat import FORCE_FINISH_MESSAGE
    assert "skill_scores" not in DEFAULT_DIAGNOSIS_PROMPT
    assert "skill_scores" not in FINAL_INSTRUCTION
    assert "skill_scores" not in FORCE_FINISH_MESSAGE


def test_grading_rules_are_holistic_not_a_ladder():
    """Placement is by overall quality, weighing free-text production most, not a
    fixed per-question ladder."""
    from src.services.aia_diagnosis_chat import DEFAULT_GRADING_RULES
    assert "OVERALL quality" in DEFAULT_GRADING_RULES
    assert "no fixed ladder" in DEFAULT_GRADING_RULES
    assert "free-text" in DEFAULT_GRADING_RULES
    # A single answer must not swing the level.
    assert "Do not over-read a single answer" in DEFAULT_GRADING_RULES


def test_grading_rules_require_production_for_high_levels():
    """Multiple choice is recognition, not production: C1/C2 must rest on the
    free-text answers, so an all-multiple-choice plan cannot mint a high level."""
    from src.services.aia_diagnosis_chat import DEFAULT_GRADING_RULES
    assert "Recognition is not production" in DEFAULT_GRADING_RULES
    assert "C1 or C2" in DEFAULT_GRADING_RULES


# ─── Parsing: interview continues (final call may still emit a running turn) ─

def test_parse_ongoing_turn():
    raw = json.dumps({"done": False, "message": "Comment vas-tu?"})
    assert parse_turn_response(raw) == {"done": False, "message": "Comment vas-tu?"}


def test_parse_strips_markdown_fence():
    raw = '```json\n{"done": false, "message": "Wie geht es dir?"}\n```'
    assert parse_turn_response(raw)["message"] == "Wie geht es dir?"


def test_parse_ongoing_turn_drops_stray_level():
    """A level only counts on the final turn; an early one must not be persisted."""
    raw = json.dumps({"done": False, "message": "Weiter?", "level": "C2"})
    assert parse_turn_response(raw) == {"done": False, "message": "Weiter?"}


def test_parse_ongoing_turn_drops_a_stray_reaction():
    """The field is gone from the model contract; a leftover one is not rendered."""
    raw = json.dumps({"done": False, "reaction": "Stark!", "message": "Weiter?"})
    assert parse_turn_response(raw) == {"done": False, "message": "Weiter?"}


# ─── Parsing: final verdict ────────────────────────────────────────────────

def _final(**overrides) -> str:
    payload = {
        "done": True,
        "message": "Gut gemacht.",
        "level": "B1",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_parse_final_turn():
    result = parse_turn_response(_final())
    assert result == {"done": True, "level": "B1", "message": "Gut gemacht."}


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


@pytest.mark.parametrize("level", ["A1", "A2", "B1", "B2", "C1", "C2"])
def test_parse_accepts_every_cefr_level(level):
    assert parse_turn_response(_final(level=level))["level"] == level


@pytest.mark.parametrize("level", ["B1+", "B3", "A0", "D1", "c1", ""])
def test_parse_rejects_levels_outside_the_ladder(level):
    """B1+ is gone; only the six canonical CEFR codes are accepted."""
    with pytest.raises(DiagnosisChatError):
        parse_turn_response(_final(level=level))


def test_parse_accepts_a_final_turn_without_scores():
    """The five per-skill scores are gone: an answer without them is complete.

    They used to be mandatory, so a model that dropped one failed the whole
    grading turn and cost a repair call for a number nobody read.
    """
    result = parse_turn_response(_final())
    assert result["done"] is True
    assert "skill_scores" not in result


# ─── Final grading messages ────────────────────────────────────────────────

def test_build_final_messages_carries_the_record_to_one_user_turn():
    plan = [{"band": "A1", "type": "choice", "text": "Ich ___ Student.",
             "options": [{"text": "bin", "correct": True},
                         {"text": "ist", "correct": False}]}]
    history = [
        {"role": "assistant", "content": "Ich ___ Student.", "options": ["ist", "bin"]},
        {"role": "user", "content": "bin", "selected": ["bin"]},
    ]
    messages = build_final_messages("SYS", plan, history)
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == "SYS"
    assert FINAL_INSTRUCTION.split(".")[0] in messages[1]["content"]
    # The record (with the code-graded RESULT) rides in the user turn.
    assert "RESULT (already graded" in messages[1]["content"]


# ─── Plan shape ────────────────────────────────────────────────────────────

def test_plan_is_twelve_written_out_slots():
    assert QUESTION_COUNT == 12
    # Fragen tragen keine Stufe, nur eine Aufgabenart, und jede ist ausgeschrieben.
    assert all("text" in step for step in DEFAULT_GERMAN_QUESTION_PLAN)
    assert all("band" not in step for step in DEFAULT_GERMAN_QUESTION_PLAN)
    types = [step["type"] for step in DEFAULT_GERMAN_QUESTION_PLAN]
    assert set(types) == {"choice", "free text"}
    # At least two slots the AI judges, since free writing carries the placement.
    assert count_judged_questions(DEFAULT_GERMAN_QUESTION_PLAN) >= 2


# ─── Admin-configurable question plan (old shapes stay valid) ──────────────

def test_parse_question_plan_empty_returns_default():
    assert parse_question_plan("") == DEFAULT_GERMAN_QUESTION_PLAN
    assert parse_question_plan("   ") == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_question_plan_invalid_json_returns_default():
    assert parse_question_plan("{not json") == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_question_plan_rejects_bad_type():
    bad_type = json.dumps([{"type": "essay", "text": "Was auch immer."}])
    assert parse_question_plan(bad_type) == DEFAULT_GERMAN_QUESTION_PLAN


def test_parse_question_plan_ignores_a_legacy_band():
    """Older plans carried a CEFR band; it is now stripped, not rejected."""
    raw = json.dumps([{"band": "A1", "type": "free writing", "text": "Schreibe etwas."},
                      {"band": "C2", "type": "free writing", "text": "Schreibe mehr."}])
    assert parse_question_plan(raw) == [
        {"type": "free text", "text": "Schreibe etwas."},
        {"type": "free text", "text": "Schreibe mehr."},
    ]


def test_parse_question_plan_accepts_a_written_out_plan():
    raw = json.dumps([
        {"type": "free text", "text": "Ich ___ zur Arbeit.", "answers": ["gehe"]},
        {"type": "free text", "text": "Schreibe drei Sätze über deinen Tag."},
    ])
    assert parse_question_plan(raw) == [
        {"type": "free text", "text": "Ich ___ zur Arbeit.", "answers": ["gehe"]},
        {"type": "free text", "text": "Schreibe drei Sätze über deinen Tag."},
    ]


# ─── Grading rules + calibration examples ──────────────────────────────────

def test_parse_level_examples_empty_returns_defaults():
    from src.services.aia_diagnosis_chat import parse_level_examples, DEFAULT_LEVEL_EXAMPLES
    assert parse_level_examples("") == DEFAULT_LEVEL_EXAMPLES
    assert parse_level_examples("   ") == DEFAULT_LEVEL_EXAMPLES


def test_parse_level_examples_merges_partial_override_onto_defaults():
    from src.services.aia_diagnosis_chat import parse_level_examples, DEFAULT_LEVEL_EXAMPLES
    out = parse_level_examples(json.dumps({"A2": "Mein eigenes A2 Beispiel."}))
    assert out["A2"] == "Mein eigenes A2 Beispiel."
    assert out["A1"] == DEFAULT_LEVEL_EXAMPLES["A1"]
    assert out["B1"] == DEFAULT_LEVEL_EXAMPLES["B1"]
    assert out["B2"] == DEFAULT_LEVEL_EXAMPLES["B2"]


def test_parse_level_examples_ignores_unknown_keys_and_bad_json():
    from src.services.aia_diagnosis_chat import parse_level_examples, DEFAULT_LEVEL_EXAMPLES
    assert parse_level_examples("{oops") == DEFAULT_LEVEL_EXAMPLES
    out = parse_level_examples(json.dumps({"D1": "nope", "A1": "Ja."}))
    assert "D1" not in out
    assert out["A1"] == "Ja."


def test_build_examples_block_lists_every_example():
    from src.services.aia_diagnosis_chat import build_examples_block, DEFAULT_LEVEL_EXAMPLES
    block = build_examples_block(DEFAULT_LEVEL_EXAMPLES)
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        assert f"- {level}:" in block
    assert "Am Samstag gehe ich ins Kino." in block
    assert "Ich arbeite in einem Büro." in block
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


def test_example_items_splits_on_dash_and_newline_keeps_hyphen_word():
    from src.services.aia_diagnosis_chat import example_items
    assert example_items("-- Satz eins.\n-- Satz zwei.") == ["Satz eins.", "Satz zwei."]
    assert example_items("Eins. -- Zwei.") == ["Eins.", "Zwei."]
    assert example_items("Ich schreibe eine E-Mail.") == ["Ich schreibe eine E-Mail."]
    assert example_items("") == []


def test_assemble_system_prompt_fills_both_placeholders():
    from src.services.aia_diagnosis_chat import (
        assemble_system_prompt, DEFAULT_DIAGNOSIS_PROMPT, DEFAULT_GRADING_RULES,
        DEFAULT_LEVEL_EXAMPLES, GRADING_PLACEHOLDER, LEVELS_PLACEHOLDER,
        EXAMPLES_PLACEHOLDER,
    )
    from src.services.aia_level_ladder import DEFAULT_LEVEL_DESCRIPTIONS
    out = assemble_system_prompt(
        DEFAULT_DIAGNOSIS_PROMPT, DEFAULT_GRADING_RULES, DEFAULT_LEVEL_DESCRIPTIONS,
        DEFAULT_LEVEL_EXAMPLES, "German",
    )
    assert GRADING_PLACEHOLDER not in out
    assert LEVELS_PLACEHOLDER not in out
    assert EXAMPLES_PLACEHOLDER not in out
    assert "{language}" not in out
    assert "LEVEL ASSIGNMENT" in out
    assert "CALIBRATION EXAMPLES" in out
    assert "Am Samstag gehe ich ins Kino." in out
    assert DEFAULT_LEVEL_DESCRIPTIONS["B1"] in out


def test_assemble_system_prompt_appends_when_placeholders_missing():
    from src.services.aia_diagnosis_chat import (
        assemble_system_prompt, DEFAULT_GRADING_RULES, DEFAULT_LEVEL_EXAMPLES,
    )
    from src.services.aia_level_ladder import DEFAULT_LEVEL_DESCRIPTIONS
    out = assemble_system_prompt(
        "A custom prompt with no placeholders.", DEFAULT_GRADING_RULES,
        DEFAULT_LEVEL_DESCRIPTIONS, DEFAULT_LEVEL_EXAMPLES, "German",
    )
    assert "LEVEL ASSIGNMENT" in out
    assert "CALIBRATION EXAMPLES" in out
    assert "Am Samstag gehe ich ins Kino." in out
    assert "These describe a typical learner at each outcome:" in out
    assert DEFAULT_LEVEL_DESCRIPTIONS["A1"] in out


def test_default_prompt_carries_both_placeholders_once():
    from src.services.aia_diagnosis_chat import (
        DEFAULT_DIAGNOSIS_PROMPT, GRADING_PLACEHOLDER, EXAMPLES_PLACEHOLDER,
    )
    assert DEFAULT_DIAGNOSIS_PROMPT.count(GRADING_PLACEHOLDER) == 1
    assert DEFAULT_DIAGNOSIS_PROMPT.count(EXAMPLES_PLACEHOLDER) == 1


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


def test_question_count_is_twelve():
    assert QUESTION_COUNT == 12


def test_diagnosis_config_defaults(monkeypatch):
    import asyncio
    from src.features.ai_assistant.routes.language_training import diagnosis as route
    monkeypatch.setattr(route.db, "get_setting", lambda key, default="": default)
    out = asyncio.run(route.config(current_user={"user_id": 1}))
    assert out["question_count"] == QUESTION_COUNT
    assert out["answer_max_chars"] == 2000


# ─── Stufen-Leiter: die Beschreibungen kommen aus der Karte ──────────────────

def test_prompt_carries_the_levels_placeholder():
    """Die Stufen-Beschreibungen kommen aus der Karte, nicht aus dem Prompt-Text."""
    from src.services.aia_diagnosis_chat import LEVELS_PLACEHOLDER
    assert LEVELS_PLACEHOLDER in DEFAULT_DIAGNOSIS_PROMPT
    assert "These describe a typical learner at each outcome:" in DEFAULT_DIAGNOSIS_PROMPT


def test_grading_rules_no_longer_carry_the_level_list():
    """Die Liste steht jetzt in der Stufen-Leiter, nicht mehr doppelt hier."""
    from src.services.aia_diagnosis_chat import DEFAULT_GRADING_RULES
    assert "These describe a typical learner" not in DEFAULT_GRADING_RULES
    assert "- A1:" not in DEFAULT_GRADING_RULES
    assert "- C2:" not in DEFAULT_GRADING_RULES
    # Das Verfahren bleibt vollstaendig.
    assert "OVERALL quality" in DEFAULT_GRADING_RULES
    assert "Recognition is not production" in DEFAULT_GRADING_RULES


def test_assemble_fills_the_levels_block():
    from src.services.aia_diagnosis_chat import assemble_system_prompt
    out = assemble_system_prompt(
        "LEVEL ASSIGNMENT\n{grading}\n\nLadder:\n{levels}\n\nEx:\n{examples}\nSprache {language}.",
        "Regeln.",
        {"A1": "Ganz einfach.", "B1": "Mittel."},
        {"A1": "Ein Satz."},
        "Deutsch",
    )
    assert "- A1: Ganz einfach." in out
    assert "- B1: Mittel." in out
    assert "{levels}" not in out
    assert "Sprache Deutsch." in out


def test_assemble_appends_the_levels_block_when_the_placeholder_is_gone():
    """Ein angepasster Prompt darf die Stufen nicht verlieren."""
    from src.services.aia_diagnosis_chat import assemble_system_prompt
    out = assemble_system_prompt(
        "Nur Text ohne Platzhalter.",
        "Regeln.",
        {"A1": "Ganz einfach."},
        {"A1": "Ein Satz."},
        "Deutsch",
    )
    assert "These describe a typical learner at each outcome:" in out
    assert "- A1: Ganz einfach." in out


def test_legacy_grading_rules_are_recognised_as_the_old_default():
    """Wer den Text angefasst und zurueckgesetzt hat, bekommt den neuen Standard."""
    from src.services.aia_diagnosis_chat import (
        DEFAULT_GRADING_RULES,
        _LEGACY_GRADING_RULES,
    )
    from src.services.aia_level_ladder import resolve_prompt_setting
    assert "- A1:" in _LEGACY_GRADING_RULES
    assert resolve_prompt_setting(
        _LEGACY_GRADING_RULES, _LEGACY_GRADING_RULES, DEFAULT_GRADING_RULES
    ) == DEFAULT_GRADING_RULES
