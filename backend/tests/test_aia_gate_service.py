from src.features.ai_assistant.scheduling.gate_service import (
    _config,
    gate_acquire,
    gate_enabled,
)


def test_gate_disabled_by_default():
    assert gate_enabled(get_setting=lambda k, d="": d) is False
    assert gate_enabled(get_setting=lambda k, d="": "false") is False
    assert gate_enabled(get_setting=lambda k, d="": "true") is True
    assert gate_enabled(get_setting=lambda k, d="": "TRUE") is True


def test_config_defaults():
    g, w = _config(lambda k, d="": d)
    assert g == 2.0
    assert w == {"chat": 2.0, "ingest": 1.0, "studio": 1.0}


def test_config_custom():
    s = {"aia_gate_global_per_sec": "5", "aia_gate_weight_chat": "3"}
    g, w = _config(lambda k, d="": s.get(k, d))
    assert g == 5.0
    assert w["chat"] == 3.0
    assert w["ingest"] == 1.0


def test_gate_acquire_is_noop_when_disabled():
    # disabled -> returns True immediately, never builds a Redis-backed gate
    assert gate_acquire("chat", get_setting=lambda k, d="": "false") is True
    assert gate_acquire("studio", get_setting=lambda k, d="": "false") is True
