"""Checks the chat provider-failover policy and client chain building."""

from src.features.ai_assistant.routes import _chat_failover as fo
from src.services.feature_router import FeatureBinding


class _UpstreamBusy(Exception):
    status_code = 503


def test_failover_on_transient_error_with_no_output_and_more_providers():
    assert fo.should_failover(_UpstreamBusy(), has_output=False, is_last_provider=False) is True


def test_no_failover_once_output_started():
    assert fo.should_failover(_UpstreamBusy(), has_output=True, is_last_provider=False) is False


def test_no_failover_on_last_provider():
    assert fo.should_failover(_UpstreamBusy(), has_output=False, is_last_provider=True) is False


def test_no_failover_on_non_transient_error():
    assert fo.should_failover(ValueError("bad request"), has_output=False, is_last_provider=False) is False


def test_build_client_chain_appends_fallback_clients(monkeypatch):
    fallback_binding = FeatureBinding(
        feature="chat",
        provider={"id": 21, "name": "P21", "base_url": "http://p21", "api_key": None, "protocol": "openai_compat"},
        model="other-model",
    )
    monkeypatch.setattr(fo.feature_provider_choices, "fallback_candidates", lambda feature: [fallback_binding])
    built = []
    monkeypatch.setattr(fo.feature_router, "make_llm_client", lambda b: built.append(b) or f"client-for-{b.provider['id']}")

    primary = "primary-client"
    chain = fo.build_client_chain(primary)

    assert chain == ["primary-client", "client-for-21"]
    assert built == [fallback_binding]


def test_build_client_chain_no_fallbacks_is_just_the_primary(monkeypatch):
    monkeypatch.setattr(fo.feature_provider_choices, "fallback_candidates", lambda feature: [])

    assert fo.build_client_chain("primary-client") == ["primary-client"]
