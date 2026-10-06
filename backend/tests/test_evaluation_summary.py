"""The numbers behind the statistics tab, counted without any account behind them."""
from datetime import datetime

from src.features.evaluation.service import summarize

FRAGEN = [
    {"id": "q1", "type": "choice", "text": "Wie einfach war die Bedienung?", "options": ["Leicht", "Schwer"]},
    {"id": "q2", "type": "multi", "text": "Welche Tools?", "options": ["Karteikarten", "Quiz"]},
    {"id": "q3", "type": "text", "text": "Was hat gefehlt?"},
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
    assert ergebnis["questions"][0]["answered"] == 0


def test_choice_question_gets_a_distribution():
    ergebnis = summarize(
        [_antwort(1, q1="Leicht"), _antwort(2, q1="Schwer"), _antwort(3, q1="Leicht")],
        FRAGEN,
    )
    frage = ergebnis["questions"][0]
    assert frage["answered"] == 3
    assert frage["distribution"] == {"Leicht": 2, "Schwer": 1}


def test_multi_question_counts_every_pick_across_one_answer():
    ergebnis = summarize(
        [_antwort(1, q2=["Karteikarten", "Quiz"]), _antwort(2, q2=["Karteikarten"])],
        FRAGEN,
    )
    frage = ergebnis["questions"][1]
    assert frage["answered"] == 2
    assert frage["distribution"] == {"Karteikarten": 2, "Quiz": 1}


def test_a_skipped_question_gets_its_own_bucket():
    ergebnis = summarize([_antwort(1, q1="Leicht"), _antwort(2, q1="not_tested")], FRAGEN)
    frage = ergebnis["questions"][0]
    assert frage["distribution"] == {"Leicht": 1, "Schwer": 0, "not_tested": 1}


def test_no_skip_bucket_when_nobody_skipped():
    ergebnis = summarize([_antwort(1, q1="Leicht")], FRAGEN)
    assert "not_tested" not in ergebnis["questions"][0]["distribution"]


def test_text_question_collects_the_wording():
    ergebnis = summarize([_antwort(1, q3="Mehr Beispiele"), _antwort(2, q3="   ")], FRAGEN)
    frage = ergebnis["questions"][2]
    assert frage["answers"] == ["Mehr Beispiele"]
    assert frage["answered"] == 1


def test_participants_are_numbered_oldest_first_and_carry_all_their_answers():
    ergebnis = summarize([_antwort(5, q1="Leicht", q3="Top"), _antwort(2, q1="Schwer", q3="Nix")], FRAGEN)
    erste, zweite = ergebnis["responses"]
    assert erste["number"] == 1
    assert erste["created_at"].day == 2
    assert {a["question_id"] for a in erste["answers"]} == {"q1", "q3"}
    assert zweite["number"] == 2


def test_answers_to_deleted_questions_are_left_out():
    ergebnis = summarize([_antwort(1, q1="Leicht", weg="alt")], FRAGEN)
    assert ergebnis["questions"][0]["answered"] == 1
    assert len(ergebnis["questions"]) == 3
