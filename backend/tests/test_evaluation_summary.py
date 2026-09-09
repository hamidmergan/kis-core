"""The numbers behind the statistics tab, counted without any account behind them."""
from datetime import datetime

from src.features.evaluation.service import summarize

FRAGEN = [
    {"id": "q1", "type": "scale", "text": "Wie einfach war die Bedienung?"},
    {"id": "q2", "type": "text", "text": "Was hat gefehlt?"},
]


def _antwort(tag: int, **werte):
    return {
        "created_at": datetime(2026, 9, tag, 10, 0, 0),
        "answers": [{"question_id": k, "value": v} for k, v in werte.items()],
    }


def test_empty_evaluation_counts_to_zero():
    ergebnis = summarize([], FRAGEN)
    assert ergebnis["total"] == 0
    assert ergebnis["responses"] == []
    assert ergebnis["questions"][0]["average"] is None


def test_scale_question_gets_average_and_distribution():
    ergebnis = summarize([_antwort(1, q1=4), _antwort(2, q1=2), _antwort(3, q1=4)], FRAGEN)
    frage = ergebnis["questions"][0]
    assert frage["answered"] == 3
    assert frage["average"] == 3.33
    assert frage["distribution"] == {1: 0, 2: 1, 3: 0, 4: 2, 5: 0}


def test_text_question_collects_the_wording():
    ergebnis = summarize([_antwort(1, q2="Mehr Beispiele"), _antwort(2, q2="   ")], FRAGEN)
    frage = ergebnis["questions"][1]
    assert frage["answers"] == ["Mehr Beispiele"]
    assert frage["answered"] == 1


def test_participants_are_numbered_oldest_first_and_carry_all_their_answers():
    ergebnis = summarize([_antwort(5, q1=5, q2="Top"), _antwort(2, q1=1, q2="Nix")], FRAGEN)
    erste, zweite = ergebnis["responses"]
    assert erste["number"] == 1
    assert erste["created_at"].day == 2
    assert {a["question_id"] for a in erste["answers"]} == {"q1", "q2"}
    assert zweite["number"] == 2


def test_answers_to_deleted_questions_are_left_out():
    ergebnis = summarize([_antwort(1, q1=3, weg="alt")], FRAGEN)
    assert ergebnis["questions"][0]["answered"] == 1
    assert len(ergebnis["questions"]) == 2
