"""Bigger packets for the verdicts, with the answer room and the patience they need."""

import json
import types
from datetime import date

from src.features.ai_assistant.tasks.studio.schedule import _classify as mod


def _recording_client(calls: list):
    def create(model, messages, **kwargs):
        calls.append(kwargs)
        ids = [c["id"] for c in json.loads(messages[1]["content"].split("Candidates:\n", 1)[1])]
        content = json.dumps({"results": [{"id": i} for i in ids]})
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def _cands(n: int) -> list[dict]:
    return [{"date_raw": "14.03.2026", "date_iso": "2026-03-14", "context": "x",
             "partial_date": None, "date_precision": "day", "is_tbd": False}
            for _ in range(n)]


def test_60_candidates_go_out_in_a_single_request():
    calls: list = []
    mod._classify_candidates(_recording_client(calls), "m", _cands(60), date(2026, 9, 14))
    assert len(calls) == 1


def test_61_candidates_need_a_second_request():
    # Measured: compact verdicts hold at 60 and collapse at 120, real appointments vanish.
    calls: list = []
    mod._classify_candidates(_recording_client(calls), "m", _cands(61), date(2026, 9, 14))
    assert len(calls) == 2


def test_the_answer_room_leaves_headroom_for_a_full_packet():
    # Measured: 60 compact verdicts took 1.921 tokens, spelled out they would take about 6.000.
    calls: list = []
    mod._classify_candidates(_recording_client(calls), "m", _cands(60), date(2026, 9, 14))
    assert calls[0]["max_tokens"] >= 16000


def test_a_packet_gets_the_time_a_slow_provider_needs():
    # Measured: the same packet took 9 s and 63 s on different minutes of the same day.
    calls: list = []
    mod._classify_candidates(_recording_client(calls), "m", _cands(60), date(2026, 9, 14))
    assert calls[0]["timeout"] >= 600
