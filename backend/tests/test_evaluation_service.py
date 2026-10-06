"""Pure rules for the evaluation: question and answer validation."""
import pytest

from src.features.evaluation.service import (
    MAX_OPTION_CHARS,
    default_config,
    validate_answers,
    validate_questions,
)


def test_default_config_ships_a_working_example():
    config = default_config()
    assert config["title"]
    assert len(config["questions"]) >= 1
    for frage in config["questions"]:
        assert frage["type"] in ("choice", "multi", "text")
        assert frage["text"]


def test_default_config_question_ids_are_stable_across_calls():
    """Regression: random ids per call meant a submission's answers never matched
    the questions read back moments later, as long as nothing was saved yet."""
    erster_aufruf = [f["id"] for f in default_config()["questions"]]
    zweiter_aufruf = [f["id"] for f in default_config()["questions"]]
    assert erster_aufruf == zweiter_aufruf


def test_default_config_choice_and_multi_have_at_least_two_options():
    for frage in default_config()["questions"]:
        if frage["type"] in ("choice", "multi"):
            assert len(frage["options"]) >= 2, frage["text"]


def test_default_config_show_if_points_at_an_existing_question():
    ids = {f["id"] for f in default_config()["questions"]}
    for frage in default_config()["questions"]:
        if "show_if" in frage:
            assert frage["show_if"]["question_id"] in ids, frage["text"]


def test_validate_questions_rejects_an_empty_list():
    with pytest.raises(ValueError):
        validate_questions([])


def test_validate_questions_rejects_an_unknown_type():
    with pytest.raises(ValueError):
        validate_questions([{"type": "essay", "text": "Wie war's?"}])


def test_validate_questions_rejects_blank_text():
    with pytest.raises(ValueError):
        validate_questions([{"type": "text", "text": "   "}])


def test_validate_questions_trims_and_fills_missing_ids():
    fragen = validate_questions([{"type": "text", "text": "  Wie war's?  "}])
    assert fragen[0]["text"] == "Wie war's?"
    assert fragen[0]["id"]


def test_validate_questions_keeps_a_given_id():
    fragen = validate_questions([{"id": "q1", "type": "text", "text": "Was fehlt?"}])
    assert fragen[0]["id"] == "q1"


def test_validate_questions_trims_the_options():
    fragen = validate_questions([
        {"type": "choice", "text": "Wie war's?", "options": ["  Gut ", "Schlecht  "]},
    ])
    assert fragen[0]["options"] == ["Gut", "Schlecht"]


def test_validate_questions_rejects_fewer_than_two_options():
    with pytest.raises(ValueError):
        validate_questions([{"type": "choice", "text": "Wie war's?", "options": ["Nur eine"]}])


def test_validate_questions_rejects_an_overlong_option():
    with pytest.raises(ValueError):
        validate_questions([
            {"type": "choice", "text": "Wie war's?", "options": ["Gut", "x" * (MAX_OPTION_CHARS + 1)]},
        ])


def test_validate_questions_drops_options_on_a_text_question():
    fragen = validate_questions([
        {"type": "text", "text": "Was fehlt?", "options": ["Gut", "Schlecht"]},
    ])
    assert "options" not in fragen[0]


def test_validate_questions_keeps_a_show_if():
    fragen = validate_questions([
        {"type": "choice", "text": "Bereich?", "options": ["A", "B"]},
        {"type": "text", "text": "Mehr dazu?", "show_if": {"question_id": "x", "in": ["A"]}},
    ])
    assert fragen[1]["show_if"] == {"question_id": "x", "in": ["A"]}


def test_validate_questions_rejects_a_show_if_without_values():
    with pytest.raises(ValueError):
        validate_questions([
            {"type": "text", "text": "Mehr dazu?", "show_if": {"question_id": "x", "in": []}},
        ])


def test_validate_answers_drops_answers_to_questions_that_no_longer_exist():
    fragen = [{"id": "q1", "type": "text", "text": "Was fehlt?"}]
    antworten = validate_answers(
        [{"question_id": "q1", "value": "Nichts"}, {"question_id": "gone", "value": "x"}],
        fragen,
    )
    assert antworten == [{"question_id": "q1", "value": "Nichts"}]


def test_validate_answers_drops_blank_text_answers():
    fragen = [
        {"id": "q1", "type": "text", "text": "Was fehlt?"},
        {"id": "q2", "type": "text", "text": "Sonst noch was?"},
    ]
    antworten = validate_answers(
        [{"question_id": "q1", "value": "   "}, {"question_id": "q2", "value": "Nein"}],
        fragen,
    )
    assert antworten == [{"question_id": "q2", "value": "Nein"}]


def test_validate_answers_drops_an_empty_selection():
    fragen = [
        {"id": "q1", "type": "multi", "text": "Welche?", "options": ["A", "B"]},
        {"id": "q2", "type": "text", "text": "Sonst noch was?"},
    ]
    antworten = validate_answers(
        [{"question_id": "q1", "value": []}, {"question_id": "q2", "value": "Nein"}],
        fragen,
    )
    assert antworten == [{"question_id": "q2", "value": "Nein"}]


def test_validate_answers_keeps_a_multi_selection():
    fragen = [{"id": "q1", "type": "multi", "text": "Welche?", "options": ["A", "B"]}]
    antworten = validate_answers([{"question_id": "q1", "value": ["A", "B"]}], fragen)
    assert antworten == [{"question_id": "q1", "value": ["A", "B"]}]


def test_validate_answers_requires_at_least_one():
    fragen = [{"id": "q1", "type": "text", "text": "Was fehlt?"}]
    with pytest.raises(ValueError):
        validate_answers([], fragen)
