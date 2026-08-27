"""Registry of the protocol adapters, a new protocol is registered here."""

from __future__ import annotations

from typing import Optional

from src.services.protocols.base import CAPABILITIES, ProbeResult, ProviderAdapter
from src.services.protocols.deepl import DeepLAdapter
from src.services.protocols.docling import DoclingAdapter
from src.services.protocols.openai_compat import OpenAICompatAdapter

_REGISTRY: dict[str, type[ProviderAdapter]] = {
    OpenAICompatAdapter.PROTOCOL: OpenAICompatAdapter,
    DeepLAdapter.PROTOCOL: DeepLAdapter,
    DoclingAdapter.PROTOCOL: DoclingAdapter,
}


def known_protocols() -> list[str]:
    """Protocol identifiers the admin can pick in the UI."""
    return list(_REGISTRY.keys())


def get_adapter_class(protocol: str) -> type[ProviderAdapter]:
    if protocol not in _REGISTRY:
        raise ValueError(f"Unknown protocol: {protocol!r}")
    return _REGISTRY[protocol]


def make_adapter(
    *,
    protocol: str,
    base_url: str,
    api_key: Optional[str] = None,
) -> ProviderAdapter:
    cls = get_adapter_class(protocol)
    return cls(base_url=base_url, api_key=api_key)


def fixed_capabilities(protocol: str) -> Optional[tuple[str, ...]]:
    """For protocols whose capabilities are not probe-derived."""
    return get_adapter_class(protocol).FIXED_CAPABILITIES


__all__ = [
    "CAPABILITIES",
    "DeepLAdapter",
    "DoclingAdapter",
    "OpenAICompatAdapter",
    "ProbeResult",
    "ProviderAdapter",
    "fixed_capabilities",
    "get_adapter_class",
    "known_protocols",
    "make_adapter",
]
