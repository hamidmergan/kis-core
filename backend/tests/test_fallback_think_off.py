"""A fallback provider gets its own switch against thinking, not the first choice's."""

import json

from src.services import model_limits, provider_transport as pt


def _target(pid: int) -> pt.Target:
    return pt.Target(provider_id=pid, name=f"p{pid}", root="http://x", api_key="k", model="m")


def _profile(monkeypatch, profiles: dict):
    monkeypatch.setattr(model_limits, "stored_profile", lambda pid, model: profiles.get(pid))


def test_a_thinking_fallback_gets_its_switch(monkeypatch):
    _profile(monkeypatch, {14: model_limits.ModelProfile(1000, "x", True, "chat_template_kwargs")})
    body = json.dumps({"model": "m", "messages": []}).encode()
    out = json.loads(pt._with_think_off(body, _target(14)))
    assert out["chat_template_kwargs"] == {"enable_thinking": False}


def test_the_first_choices_switch_is_swapped_for_the_fallbacks(monkeypatch):
    _profile(monkeypatch, {14: model_limits.ModelProfile(1000, "x", True, "reasoning_effort_none")})
    body = json.dumps({"model": "m", "chat_template_kwargs": {"enable_thinking": False}}).encode()
    out = json.loads(pt._with_think_off(body, _target(14)))
    assert "chat_template_kwargs" not in out
    assert out["reasoning_effort"] == "none"


def test_a_fallback_that_does_not_think_gets_no_switch(monkeypatch):
    _profile(monkeypatch, {10: model_limits.ModelProfile(1000, "x", False, "")})
    body = json.dumps({"model": "m", "reasoning_effort": "none"}).encode()
    assert json.loads(pt._with_think_off(body, _target(10))) == {"model": "m"}


def test_an_unmeasured_fallback_keeps_the_body(monkeypatch):
    _profile(monkeypatch, {})
    body = json.dumps({"model": "m", "chat_template_kwargs": {"enable_thinking": False}}).encode()
    assert pt._with_think_off(body, _target(14)) == body
