"""Checks the chat provider-failover policy and client chain building."""

from src.features.ai_assistant.routes import _chat_failover as fo


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


def test_build_client_chain_is_just_the_primary():
    """The provider door inside the client falls back, a second chain would ask the fallback twice."""
    assert fo.build_client_chain("primary-client") == ["primary-client"]
