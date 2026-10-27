"""A broken list answer keeps its complete entries instead of failing the whole set."""

import json

import pytest

from src.features.ai_assistant.tasks._json_commas import loads_entries


def test_a_clean_answer_is_read_as_it_is():
    assert loads_entries('{"title":"T","cards":[{"a":1}]}', "cards") == {"title": "T", "cards": [{"a": 1}]}


def test_a_broken_entry_is_dropped_and_the_others_stay():
    text = '{"title":"T","cards":[{"q":"a","r":"b"},{"q":"c" "r":"d"},{"q":"e","r":"f"}]}'
    assert loads_entries(text, "cards") == {"title": "T", "cards": [{"q": "a", "r": "b"},
                                                                     {"q": "e", "r": "f"}]}


def test_an_answer_cut_off_mid_entry_keeps_what_was_finished():
    text = '{"title":"T","exercises":[{"q":"a"},{"q":"b"},{"q":"c","opt'
    assert loads_entries(text, "exercises")["exercises"] == [{"q": "a"}, {"q": "b"}]


def test_without_the_list_the_error_stays():
    with pytest.raises(json.JSONDecodeError):
        loads_entries('{"title":"T" "x":1}', "cards")
