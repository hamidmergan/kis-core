"""The interface of a protocol adapter: capabilities, probing, call shape."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# Canonical capability identifiers used everywhere (UI, DB, routing).
CAPABILITIES: tuple[str, ...] = (
    "chat",
    "embedding",
    "vision",
    "ocr",
    "stt",
    "tts",
    "image_gen",
    "image_edit",
    "translation",
)


@dataclass
class ProbeResult:
    """Outcome of running a capability probe against a configured endpoint."""

    capabilities: list[str]
    status: str  # "ok" | "error"
    error: Optional[str] = None


class ProviderAdapter(ABC):
    """Base class of every adapter, capabilities fixed or from the probe."""

    PROTOCOL: str = ""
    FIXED_CAPABILITIES: Optional[tuple[str, ...]] = None

    def __init__(self, *, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @abstractmethod
    def probe(self) -> ProbeResult:
        """Run a probe against ``base_url`` and report capabilities + status."""
        ...
