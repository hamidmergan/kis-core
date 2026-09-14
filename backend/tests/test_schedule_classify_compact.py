"""A compact verdict, only the deviating fields, must read like a spelled-out one."""

import json
import types
from datetime import date

from src.features.ai_assistant.tasks.studio.schedule import _classify as mod


def _client(payload):
    def create(model, messages, **kwargs):
        content = json.dumps(payload)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def _cand(i: int) -> dict:
    return {"date_raw": f"1{i}.03.2026", "date_iso": f"2026-03-1{i}", "context": "x",
            "partial_date": None, "date_precision": "day", "is_tbd": False}


_HEUTE = date(2026, 9, 14)


def test_a_bare_id_is_a_dropped_candidate_with_defaults():
    out = mod._classify_candidates_batch(_client({"results": [{"id": 0}]}), "m",
                                         [_cand(0)], _HEUTE, set())
    assert out == [{"keep": False, "is_footer": False, "is_header": False,
                    "is_historical": False, "type": "termin", "title": "",
                    "description": None, "due_time": None, "is_range": False,
                    "end_time": None, "is_open_ended": False, "is_optional": False}]


def test_a_compact_keep_carries_only_what_it_names():
    out = mod._classify_candidates_batch(
        _client({"results": [{"id": 0, "keep": True, "type": "deadline", "title": "Klausur"}]}),
        "m", [_cand(0)], _HEUTE, set())
    assert out[0]["keep"] is True
    assert out[0]["type"] == "deadline"
    assert out[0]["title"] == "Klausur"
    assert out[0]["due_time"] is None


def test_a_compact_footer_flag_still_drops_the_candidate():
    out = mod._classify_candidates_batch(
        _client({"results": [{"id": 0, "keep": True, "is_footer": True, "title": "Stand"}]}),
        "m", [_cand(0)], _HEUTE, set())
    assert out[0]["keep"] is False
    assert out[0]["is_footer"] is True


def test_compact_and_spelled_out_answers_agree():
    kompakt = {"results": [{"id": 0, "keep": True, "type": "termin", "title": "Klausur",
                            "due_time": "10:00"},
                           {"id": 1, "is_historical": True}]}
    voll = {"results": [{"id": 0, "keep": True, "is_footer": False, "is_header": False,
                         "is_historical": False, "type": "termin", "title": "Klausur",
                         "description": None, "due_time": "10:00", "end_time": None,
                         "is_range": False, "is_open_ended": False, "is_optional": False},
                        {"id": 1, "keep": False, "is_footer": False, "is_header": False,
                         "is_historical": True, "type": None, "title": None,
                         "description": None, "due_time": None, "end_time": None,
                         "is_range": False, "is_open_ended": False, "is_optional": False}]}
    cands = [_cand(0), _cand(1)]
    assert (mod._classify_candidates_batch(_client(kompakt), "m", cands, _HEUTE, set())
            == mod._classify_candidates_batch(_client(voll), "m", cands, _HEUTE, set()))


def test_the_prompt_asks_for_compact_verdicts():
    from src.features.ai_assistant.prompts.schedule_prompts import AIA_SCHEDULE_CLASSIFY_PROMPT
    assert "COMPACT OUTPUT" in AIA_SCHEDULE_CLASSIFY_PROMPT


def _client_by_call(answers: list):
    """Answers one payload per call, in order, and records how many calls came."""
    calls: list = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = json.dumps(answers[min(len(calls) - 1, len(answers) - 1)])
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))), calls


def test_a_forgotten_id_is_asked_about_once_more():
    # First answer skips id 1, the follow-up judges it: it must not silently count as dropped.
    client, calls = _client_by_call([
        {"results": [{"id": 0}, {"id": 2}]},
        {"results": [{"id": 0, "keep": True, "type": "termin", "title": "Klausur"}]},
    ])
    out = mod._classify_candidates_batch(client, "m", [_cand(0), _cand(1), _cand(2)],
                                         _HEUTE, set())
    assert len(calls) == 2
    assert out[1]["keep"] is True
    assert out[1]["title"] == "Klausur"


def test_an_id_forgotten_twice_is_dropped_without_a_third_call():
    client, calls = _client_by_call([{"results": [{"id": 0}, {"id": 2}]}, {"results": []}])
    out = mod._classify_candidates_batch(client, "m", [_cand(0), _cand(1), _cand(2)],
                                         _HEUTE, set())
    assert len(calls) == 2
    assert out[1]["keep"] is False
