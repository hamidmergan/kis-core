"""A packet that reports nothing must not cost the rest of the source."""

import json
import types

import pytest

from src.features.ai_assistant.tasks.studio.schedule import _discover as mod


def _client(payload):
    def create(model, messages, **kwargs):
        content = payload if isinstance(payload, str) else json.dumps(payload)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def test_an_empty_object_means_nothing_found():
    """Some models answer {} instead of two empty lists."""
    found = mod._discover_batch(_client({}), "m", [(0, "x" * 100), (1, "y" * 100)])
    assert found == {0: {"tbd": None, "dates": []}, 1: {"tbd": None, "dates": []}}


def test_a_broken_answer_is_still_an_error():
    with pytest.raises(ValueError):
        mod._discover_batch(_client("keine json antwort"), "m", [(0, "x" * 100)])


def test_one_failed_packet_does_not_skip_the_rest(monkeypatch):
    versuche = []

    def batch(client, model, b):
        versuche.append(b[0][0])
        if b[0][0] == 0:
            raise ValueError("kaputt")
        return {bid: {"tbd": "spaeter", "dates": []} for bid, _ in b}

    monkeypatch.setattr(mod, "_discover_batch", batch)
    monkeypatch.setattr(mod, "_MAX_BLOCKS_PER_CALL", 1)
    found = mod._discover_in_blocks(_client({}), "m", [(0, "a" * 100), (1, "b" * 100)])
    assert versuche == [0, 1]
    assert found[1]["tbd"] == "spaeter"


def test_a_rate_limit_stops_the_source(monkeypatch):
    versuche = []

    def batch(client, model, b):
        versuche.append(b[0][0])
        raise RuntimeError("429 too many requests")

    monkeypatch.setattr(mod, "_discover_batch", batch)
    monkeypatch.setattr(mod, "_MAX_BLOCKS_PER_CALL", 1)
    mod._discover_in_blocks(_client({}), "m", [(0, "a" * 100), (1, "b" * 100)])
    assert versuche == [0]
