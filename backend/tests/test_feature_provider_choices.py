"""Capability-based provider choice service (STT + image tools).

Verifies model resolution, eligibility, binding, and the reachability-filtered
listing used by the tool dropdowns.
"""

import pytest

from src.services import feature_provider_choices as svc
from src.services.feature_router import FeatureNotConfigured


def _route(provider_id=20, model_name="primary-model", provider_models=None):
    return {
        "provider_id": provider_id,
        "model_name": model_name,
        "provider_models": provider_models or {},
    }


def _provider(pid, *, caps=("stt",), enabled=True, base_url=None):
    return {
        "id": pid,
        "name": f"P{pid}",
        "protocol": "openai_compat",
        "base_url": base_url or f"http://p{pid}",
        "api_key": None,
        "enabled": enabled,
        "capabilities": list(caps),
    }


# ─── _model_for ──────────────────────────────────────────────────────────────


def test_model_for_explicit_per_provider_wins():
    route = _route(20, "primary-model", {"21": "explicit-21"})
    assert svc._model_for(route, 21) == "explicit-21"


def test_model_for_primary_inherits_model_name():
    assert svc._model_for(_route(20, "primary-model", {}), 20) == "primary-model"


def test_model_for_non_primary_without_explicit_is_empty():
    assert svc._model_for(_route(20, "primary-model", {}), 21) == ""


# ─── is_eligible ─────────────────────────────────────────────────────────────


def test_is_eligible(monkeypatch):
    providers = [_provider(20), _provider(21), _provider(22)]
    monkeypatch.setattr(svc.db, "list_providers_with_capability", lambda cap: providers)
    # 20 is primary (inherits model_name); 21 has explicit; 22 has neither.
    monkeypatch.setattr(svc.db, "get_route", lambda f: _route(20, "m", {"21": "m21"}))

    assert svc.is_eligible("stt", 20) is True
    assert svc.is_eligible("stt", 21) is True
    assert svc.is_eligible("stt", 22) is False  # capability but no model
    assert svc.is_eligible("stt", 99) is False  # not capability-eligible


# ─── resolve_binding ─────────────────────────────────────────────────────────


def test_resolve_binding_ok(monkeypatch):
    monkeypatch.setattr(svc.db, "get_provider", lambda pid: _provider(21, caps=("vision",)))
    monkeypatch.setattr(svc.db, "get_route", lambda f: _route(20, "primary", {"21": "vl-model"}))

    binding = svc.resolve_binding("vision", 21)
    assert binding.model == "vl-model"
    assert binding.provider["id"] == 21


def test_resolve_binding_disabled(monkeypatch):
    monkeypatch.setattr(svc.db, "get_provider", lambda pid: _provider(21, enabled=False))
    monkeypatch.setattr(svc.db, "get_route", lambda f: _route())
    with pytest.raises(FeatureNotConfigured, match="unavailable"):
        svc.resolve_binding("stt", 21)


def test_resolve_binding_missing_capability(monkeypatch):
    monkeypatch.setattr(svc.db, "get_provider", lambda pid: _provider(21, caps=("chat",)))
    monkeypatch.setattr(svc.db, "get_route", lambda f: _route(21, "m", {}))
    with pytest.raises(FeatureNotConfigured, match="capability"):
        svc.resolve_binding("stt", 21)


def test_resolve_binding_no_model(monkeypatch):
    monkeypatch.setattr(svc.db, "get_provider", lambda pid: _provider(21))
    # 21 is neither primary nor has an explicit model -> no model
    monkeypatch.setattr(svc.db, "get_route", lambda f: _route(20, "primary", {}))
    with pytest.raises(FeatureNotConfigured, match="no model"):
        svc.resolve_binding("stt", 21)


# ─── list_reachable_choices ──────────────────────────────────────────────────


class _FakeAdapter:
    def __init__(self, status):
        self._status = status

    def probe(self):
        from src.services.protocols.base import ProbeResult

        return ProbeResult(capabilities=[], status=self._status, error=None)


async def test_list_reachable_filters_unreachable(monkeypatch):
    providers = [_provider(20, base_url="http://ok"), _provider(21, base_url="http://down")]
    monkeypatch.setattr(svc.db, "list_providers_with_capability", lambda cap: providers)
    monkeypatch.setattr(svc.db, "get_route", lambda f: _route(21, "m", {"20": "m20", "21": "m21"}))
    monkeypatch.setattr(
        svc,
        "make_adapter",
        lambda *, protocol, base_url, api_key: _FakeAdapter("ok" if base_url == "http://ok" else "error"),
    )

    result = await svc.list_reachable_choices("stt")
    assert [p["id"] for p in result["providers"]] == [20]
    # default (21) unreachable -> falls back to first reachable (20)
    assert result["default_id"] == 20


async def test_list_reachable_keeps_default(monkeypatch):
    providers = [_provider(20, base_url="http://a"), _provider(21, base_url="http://b")]
    monkeypatch.setattr(svc.db, "list_providers_with_capability", lambda cap: providers)
    monkeypatch.setattr(svc.db, "get_route", lambda f: _route(21, "m", {"20": "m20", "21": "m21"}))
    monkeypatch.setattr(svc, "make_adapter", lambda **kw: _FakeAdapter("ok"))

    result = await svc.list_reachable_choices("stt")
    assert {p["id"] for p in result["providers"]} == {20, 21}
    assert result["default_id"] == 21


async def test_list_reachable_empty_when_no_models(monkeypatch):
    # capability-eligible but no models configured -> nothing to offer
    monkeypatch.setattr(svc.db, "list_providers_with_capability", lambda cap: [_provider(20), _provider(21)])
    monkeypatch.setattr(svc.db, "get_route", lambda f: _route(99, "", {}))

    result = await svc.list_reachable_choices("stt")
    assert result == {"providers": [], "default_id": None}
