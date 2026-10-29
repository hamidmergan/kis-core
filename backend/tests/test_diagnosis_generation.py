"""Generate questions once with the AI, the result has to be savable right away."""

import json

import pytest

from src.services.aia_diagnosis_chat import (
    CHOICE_TYPE,
    DEFAULT_GERMAN_QUESTION_PLAN,
    FREE_TEXT_TYPE,
    DiagnosisChatError,
    first_incomplete_question,
)
from src.services.aia_diagnosis_authoring import (
    GENERATION_SLOTS,
    build_generation_messages,
    build_repair_message,
    parse_generated_plan,
)

# Three slots for the three cases, the answer key makes the difference.
SLOTS = [
    {"type": FREE_TEXT_TYPE, "answers": True, "shape": "one sentence with a blank ___"},
    {"type": CHOICE_TYPE, "answers": False, "shape": "a plain grammar item"},
    {"type": FREE_TEXT_TYPE, "answers": False, "shape": "three sentences of their own"},
]


def _answer(*questions) -> str:
    return json.dumps({"questions": list(questions)})


GAP = {"type": FREE_TEXT_TYPE, "text": "Ich ___ zur Arbeit.", "answers": ["gehe"]}
CHOICE = {
    "type": CHOICE_TYPE,
    "text": "Welches Wort passt?",
    "options": [
        {"text": "Das", "correct": True},
        {"text": "Der", "correct": False},
        {"text": "Die", "correct": False},
    ],
}
FREE = {"type": FREE_TEXT_TYPE, "text": "Schreibe drei Sätze über deinen Tag."}


# ─── The slots ──────────────────────────────────────────────────────────────

def test_the_slots_follow_the_shipped_plan():
    """Generation goes slot by slot as in the shipped set."""
    assert [s["type"] for s in GENERATION_SLOTS] == [
        s["type"] for s in DEFAULT_GERMAN_QUESTION_PLAN
    ]
    assert [s["answers"] for s in GENERATION_SLOTS] == [
        bool(s.get("answers")) for s in DEFAULT_GERMAN_QUESTION_PLAN
    ]


def test_every_slot_carries_its_own_shape():
    """The character sits on the slot, otherwise the instruction would be the same twelve times."""
    shapes = [s["shape"] for s in GENERATION_SLOTS]
    assert all(shape.strip() for shape in shapes)
    assert len(set(shapes)) > 1


# ─── The instruction to the model ───────────────────────────────────────────

def test_the_order_carries_the_level_ladder_and_the_types():
    messages = build_generation_messages("- A1: Einzelne Wörter.", "- A1: Ich heiße Ana.", SLOTS)
    order = "\n".join(m["content"] for m in messages)
    assert "Einzelne Wörter." in order
    assert "Ich heiße Ana." in order
    assert CHOICE_TYPE in order and FREE_TEXT_TYPE in order
    assert "German" in order


def test_the_order_carries_the_shape_of_every_slot():
    """Without the character the model writes the same thing twelve times."""
    order = build_generation_messages("- A1: x", "- A1: y", SLOTS)[1]["content"]
    for slot in SLOTS:
        assert slot["shape"] in order


def test_every_listed_slot_says_what_it_must_carry():
    """The requirement has to sit on every single number."""
    order = build_generation_messages("- A1: x", "- A1: y", SLOTS)[1]["content"]
    lines = [ln for ln in order.splitlines() if ln.startswith(("1.", "2.", "3."))]
    assert any(CHOICE_TYPE in ln and "options" in ln for ln in lines)
    assert any("\"answers\"" in ln for ln in lines)
    assert any("no options and no answers" in ln for ln in lines)


def test_the_repair_order_names_what_was_wrong():
    """The retry has to name the concrete reason."""
    order = build_repair_message("Question 6: needs 2..8 options")
    assert "Question 6: needs 2..8 options" in order


# ─── The model's answer ─────────────────────────────────────────────────────

def test_a_good_answer_becomes_a_plan():
    plan = parse_generated_plan(_answer(GAP, CHOICE, FREE), SLOTS)
    assert [step["type"] for step in plan] == [s["type"] for s in SLOTS]
    assert plan[0]["answers"] == ["gehe"]
    assert plan[1]["options"][0] == {"text": "Das", "correct": True}
    assert plan[2] == FREE


def test_the_result_is_savable_as_it_stands():
    """The point of the whole thing: nothing to rework."""
    plan = parse_generated_plan(_answer(GAP, CHOICE, FREE), SLOTS)
    assert first_incomplete_question(json.dumps(plan)) is None


def test_a_fenced_answer_is_tolerated():
    raw = "```json\n" + _answer(GAP, CHOICE, FREE) + "\n```"
    assert len(parse_generated_plan(raw, SLOTS)) == 3


def test_too_few_questions_are_rejected():
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan(_answer(GAP, CHOICE), SLOTS)


def test_a_wrong_type_order_is_rejected():
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan(_answer(CHOICE, GAP, FREE), SLOTS)


def test_two_correct_options_are_rejected():
    """The old bug: a distractor that is correct itself."""
    broken = {**CHOICE, "options": [
        {"text": "Das", "correct": True},
        {"text": "Dieses", "correct": True},
        {"text": "Der", "correct": False},
    ]}
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan(_answer(GAP, broken, FREE), SLOTS)


def test_no_correct_option_is_rejected():
    broken = {**CHOICE, "options": [
        {"text": "Das", "correct": False},
        {"text": "Der", "correct": False},
    ]}
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan(_answer(GAP, broken, FREE), SLOTS)


def test_a_slot_that_wants_a_solution_is_rejected_without_one():
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan(
            _answer({"type": FREE_TEXT_TYPE, "text": "Ich ___ zur Arbeit."}, CHOICE, FREE),
            SLOTS,
        )


def test_a_solution_on_a_writing_sample_is_dropped():
    """The writing sample must carry no answer key, otherwise the AI reads nothing."""
    plan = parse_generated_plan(
        _answer(GAP, CHOICE, {**FREE, "answers": ["egal"]}),
        SLOTS,
    )
    assert "answers" not in plan[2]


def test_a_question_without_text_is_rejected():
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan(_answer(GAP, CHOICE, {"type": FREE_TEXT_TYPE}), SLOTS)


def test_options_on_a_free_text_question_are_dropped():
    """A surplus field does not topple the whole run."""
    plan = parse_generated_plan(
        _answer(GAP, CHOICE, {**FREE, "options": [{"text": "x", "correct": True}]}),
        SLOTS,
    )
    assert "options" not in plan[2]


def test_prose_instead_of_json_is_rejected():
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan("Gerne! Hier sind die Fragen.", SLOTS)


# ─── The endpoint ───────────────────────────────────────────────────────────

from unittest.mock import AsyncMock, patch  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from src.routes.admin import diagnosis_plan as route  # noqa: E402

ROUTE = "src.routes.admin.diagnosis_plan"


def _for_slot(slot: dict) -> dict:
    if slot["type"] == CHOICE_TYPE:
        return dict(CHOICE)
    return dict(GAP) if slot["answers"] else dict(FREE)


def _full_answer() -> str:
    """An answer matching exactly the shipped slot sequence."""
    return json.dumps({"questions": [_for_slot(s) for s in GENERATION_SLOTS]})


async def test_the_endpoint_returns_a_plan_without_saving_it(monkeypatch):
    """Management should read first and then save themselves."""
    saved = []
    monkeypatch.setattr(route.db, "get_setting", lambda key, default="": default)
    monkeypatch.setattr(route.db, "set_setting", lambda key, value: saved.append(key))

    with patch(f"{ROUTE}._ask", new=AsyncMock(return_value=_full_answer())) as ask:
        out = await route.generate_diagnosis_plan(None, object(), "de")

    assert [q["type"] for q in out["questions"]] == [s["type"] for s in GENERATION_SLOTS]
    assert first_incomplete_question(json.dumps(out["questions"])) is None
    assert ask.await_count == 1
    assert saved == []


async def test_a_broken_answer_is_repaired_once(monkeypatch):
    monkeypatch.setattr(route.db, "get_setting", lambda key, default="": default)

    answers = ["Gerne, hier kommt der Test!", _full_answer()]
    with patch(f"{ROUTE}._ask", new=AsyncMock(side_effect=answers)) as ask:
        out = await route.generate_diagnosis_plan(None, object(), "de")

    assert ask.await_count == 2
    assert len(out["questions"]) == len(GENERATION_SLOTS)


async def test_the_repair_turn_tells_the_model_what_broke(monkeypatch):
    """Otherwise it repeats the same mistake, measured by the exercise kind."""
    monkeypatch.setattr(route.db, "get_setting", lambda key, default="": default)

    half = json.loads(_full_answer())
    del half["questions"][5]["options"]  # slot 6 is a multiple-choice task
    answers = [json.dumps(half), _full_answer()]

    with patch(f"{ROUTE}._ask", new=AsyncMock(side_effect=answers)) as ask:
        await route.generate_diagnosis_plan(None, object(), "de")

    second_call = "\n".join(m["content"] for m in ask.await_args_list[1].args[1])
    assert "Question 6" in second_call
    assert "options" in second_call


async def test_a_hopeless_model_gives_up_with_502(monkeypatch):
    monkeypatch.setattr(route.db, "get_setting", lambda key, default="": default)

    with patch(f"{ROUTE}._ask", new=AsyncMock(return_value="nein danke")):
        with pytest.raises(HTTPException) as exc:
            await route.generate_diagnosis_plan(None, object(), "de")

    assert exc.value.status_code == 502
