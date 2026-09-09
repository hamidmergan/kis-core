"""Pure rules for the evaluation: question and answer validation."""
import pytest

from src.features.evaluation.service import (
    MAX_SCALE_LABEL_CHARS,
    default_config,
    validate_answers,
    validate_questions,
)


def test_default_config_ships_a_working_example():
    config = default_config()
    assert config["title"]
    assert len(config["questions"]) >= 1
    for frage in config["questions"]:
        assert frage["type"] in ("scale", "text")
        assert frage["text"]


def test_default_config_question_ids_are_stable_across_calls():
    """Regression: random ids per call meant a submission's answers never matched
    the questions read back moments later, as long as nothing was saved yet."""
    erster_aufruf = [f["id"] for f in default_config()["questions"]]
    zweiter_aufruf = [f["id"] for f in default_config()["questions"]]
    assert erster_aufruf == zweiter_aufruf


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
    fragen = validate_questions([{"type": "scale", "text": "  Wie war's?  "}])
    assert fragen[0]["text"] == "Wie war's?"
    assert fragen[0]["id"]


def test_validate_questions_keeps_a_given_id():
    fragen = validate_questions([{"id": "q1", "type": "text", "text": "Was fehlt?"}])
    assert fragen[0]["id"] == "q1"


def test_validate_questions_keeps_the_scale_labels():
    fragen = validate_questions([
        {"type": "scale", "text": "Wie einfach?", "scale_low": "  umständlich ", "scale_high": "sehr einfach"},
    ])
    assert fragen[0]["scale_low"] == "umständlich"
    assert fragen[0]["scale_high"] == "sehr einfach"


def test_validate_questions_leaves_the_scale_labels_empty_when_none_were_given():
    fragen = validate_questions([{"type": "scale", "text": "Wie einfach?"}])
    assert fragen[0]["scale_low"] == ""
    assert fragen[0]["scale_high"] == ""


def test_validate_questions_drops_scale_labels_on_a_text_question():
    fragen = validate_questions([{"type": "text", "text": "Was fehlt?", "scale_low": "gar nicht"}])
    assert "scale_low" not in fragen[0]


def test_validate_questions_rejects_an_overlong_scale_label():
    with pytest.raises(ValueError):
        validate_questions([
            {"type": "scale", "text": "Wie einfach?", "scale_high": "x" * (MAX_SCALE_LABEL_CHARS + 1)},
        ])


def test_default_config_labels_both_ends_of_every_scale():
    for frage in default_config()["questions"]:
        if frage["type"] == "scale":
            assert frage["scale_low"] and frage["scale_high"], frage["text"]


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


def test_validate_answers_requires_at_least_one():
    fragen = [{"id": "q1", "type": "text", "text": "Was fehlt?"}]
    with pytest.raises(ValueError):
        validate_answers([], fragen)
