"""Fragen einmalig von der KI erzeugen lassen, im Adminbereich.

Der Gegenentwurf zum frueheren Erzeugen waehrend des Tests: ein Aufruf, das
Ergebnis landet als ganz normale Zeilen im Fragen-Plan, die Verwaltung liest und
korrigiert es, und danach laeuft jeder Test ohne Modellaufruf.

Deshalb ist die Pruefung hier streng. Was der Aufruf zurueckgibt, muss ohne
weitere Handgriffe speicherbar sein, sonst haette die Verwaltung eine Liste, die
der Speicherweg gleich wieder ablehnt.
"""

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

# Drei Plaetze, die alle drei Faelle abdecken: Auswahl, Freitext MIT Loesung und
# Freitext OHNE. Seit es nur noch zwei Aufgabenarten gibt, ist die Loesung der
# Unterschied, nicht der Name.
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


# ─── Die Plaetze ────────────────────────────────────────────────────────────

def test_the_slots_follow_the_shipped_plan():
    """Erzeugt wird Platz fuer Platz wie im ausgelieferten Satz, also leicht nach
    schwer und mit genug Schreibproben. Die Loesungs-Flags muessen mitwandern,
    sonst waere Platz 1 auf einmal eine Schreibprobe statt einer Luecke."""
    assert [s["type"] for s in GENERATION_SLOTS] == [
        s["type"] for s in DEFAULT_GERMAN_QUESTION_PLAN
    ]
    assert [s["answers"] for s in GENERATION_SLOTS] == [
        bool(s.get("answers")) for s in DEFAULT_GERMAN_QUESTION_PLAN
    ]


def test_every_slot_carries_its_own_shape():
    """Mit nur zwei Aufgabenarten waere der Auftrag sonst zwoelfmal derselbe Satz
    und der Fragensatz eintoenig. Der Charakter steht jetzt am Platz."""
    shapes = [s["shape"] for s in GENERATION_SLOTS]
    assert all(shape.strip() for shape in shapes)
    assert len(set(shapes)) > 1


# ─── Der Auftrag an das Modell ──────────────────────────────────────────────

def test_the_order_carries_the_level_ladder_and_the_types():
    messages = build_generation_messages("- A1: Einzelne Wörter.", "- A1: Ich heiße Ana.", SLOTS)
    order = "\n".join(m["content"] for m in messages)
    assert "Einzelne Wörter." in order
    assert "Ich heiße Ana." in order
    assert CHOICE_TYPE in order and FREE_TEXT_TYPE in order
    assert "German" in order


def test_the_order_carries_the_shape_of_every_slot():
    """Der Charakter des Platzes ist das Einzige, was zwei Freitext-Plaetze noch
    unterscheidet. Faellt er aus dem Auftrag, schreibt das Modell zwoelfmal
    dasselbe."""
    order = build_generation_messages("- A1: x", "- A1: y", SLOTS)[1]["content"]
    for slot in SLOTS:
        assert slot["shape"] in order


def test_every_listed_slot_says_what_it_must_carry():
    """Gemessen: ohne Angabe an der Zeile schrieb das Modell eine Auswahl ohne
    Optionen, zweimal hintereinander. Die Sammelregel weiter oben reicht nicht,
    die Anforderung muss an jeder einzelnen Nummer stehen."""
    order = build_generation_messages("- A1: x", "- A1: y", SLOTS)[1]["content"]
    lines = [ln for ln in order.splitlines() if ln.startswith(("1.", "2.", "3."))]
    assert any(CHOICE_TYPE in ln and "options" in ln for ln in lines)
    assert any("\"answers\"" in ln for ln in lines)
    assert any("no options and no answers" in ln for ln in lines)


def test_the_repair_order_names_what_was_wrong():
    """Der allgemeine Reparaturtext half nicht: das Modell wiederholte denselben
    Fehler. Es muss lesen koennen, welche Frage woran gescheitert ist."""
    order = build_repair_message("Question 6: needs 2..8 options")
    assert "Question 6: needs 2..8 options" in order


# ─── Die Antwort des Modells ────────────────────────────────────────────────

def test_a_good_answer_becomes_a_plan():
    plan = parse_generated_plan(_answer(GAP, CHOICE, FREE), SLOTS)
    assert [step["type"] for step in plan] == [s["type"] for s in SLOTS]
    assert plan[0]["answers"] == ["gehe"]
    assert plan[1]["options"][0] == {"text": "Das", "correct": True}
    assert plan[2] == FREE


def test_the_result_is_savable_as_it_stands():
    """Der Sinn der Sache: nichts nacharbeiten muessen."""
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
    """Der alte Fehler: ein Ablenker, der selbst richtig ist."""
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
    """Platz 3 ist die Schreibprobe, an der die Stufe haengt. Traegt sie eine
    Loesung, wuerde der Code sie pruefen und die KI bekaeme nichts zu lesen."""
    plan = parse_generated_plan(
        _answer(GAP, CHOICE, {**FREE, "answers": ["egal"]}),
        SLOTS,
    )
    assert "answers" not in plan[2]


def test_a_question_without_text_is_rejected():
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan(_answer(GAP, CHOICE, {"type": FREE_TEXT_TYPE}), SLOTS)


def test_options_on_a_free_text_question_are_dropped():
    """Ein ueberschuessiges Feld kippt nicht den ganzen Durchlauf."""
    plan = parse_generated_plan(
        _answer(GAP, CHOICE, {**FREE, "options": [{"text": "x", "correct": True}]}),
        SLOTS,
    )
    assert "options" not in plan[2]


def test_prose_instead_of_json_is_rejected():
    with pytest.raises(DiagnosisChatError):
        parse_generated_plan("Gerne! Hier sind die Fragen.", SLOTS)


# ─── Der Endpunkt ───────────────────────────────────────────────────────────

from unittest.mock import AsyncMock, patch  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from src.routes.admin import diagnosis_plan as route  # noqa: E402

ROUTE = "src.routes.admin.diagnosis_plan"


def _for_slot(slot: dict) -> dict:
    if slot["type"] == CHOICE_TYPE:
        return dict(CHOICE)
    return dict(GAP) if slot["answers"] else dict(FREE)


def _full_answer() -> str:
    """Eine Antwort, die genau zur ausgelieferten Platz-Folge passt."""
    return json.dumps({"questions": [_for_slot(s) for s in GENERATION_SLOTS]})


async def test_the_endpoint_returns_a_plan_without_saving_it(monkeypatch):
    """Die Verwaltung soll erst lesen und dann selbst speichern."""
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
    """Sonst wiederholt es denselben Fehler, gemessen an der Aufgabenart situation."""
    monkeypatch.setattr(route.db, "get_setting", lambda key, default="": default)

    half = json.loads(_full_answer())
    del half["questions"][5]["options"]  # Platz 6 ist eine Auswahl-Aufgabe
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
