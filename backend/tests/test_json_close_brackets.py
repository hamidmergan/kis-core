"""The forgotten closing bracket, the second JSON slip of a local model."""

import json

from src.features.ai_assistant.tasks._json_commas import close_brackets
from src.features.ai_assistant.tasks._helpers import _clean_llm_json


def test_a_missing_bracket_before_the_last_brace_is_added():
    # Mind map 819 on gemma4:31b, 08.10.2026: both attempts ended in "}\n}".
    roh = '{"topic": "T", "children": [{"topic": "A"}, {"topic": "B"}\n}'
    assert json.loads(close_brackets(roh)) == {"topic": "T", "children": [{"topic": "A"}, {"topic": "B"}]}


def test_valid_json_stays_untouched():
    roh = '{"a": [1, {"b": "x]}"}], "c": "{["}'
    assert close_brackets(roh) == roh


def test_brackets_inside_strings_count_for_nothing():
    roh = '{"a": ["]", "}"}'
    assert json.loads(close_brackets(roh)) == {"a": ["]", "}"]}


def test_a_stray_closer_is_left_out():
    assert json.loads(close_brackets('{"a": 1}]')) == {"a": 1}


def test_the_tools_clean_up_the_slip_as_well():
    roh = '```json\n{"cards": [{"question": "F", "answer": "A"},\n}\n```'
    assert json.loads(_clean_llm_json(roh)) == {"cards": [{"question": "F", "answer": "A"}]}
