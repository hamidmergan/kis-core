"""Protocol adapter interface.

A protocol adapter is the code-side definition of one AI-provider protocol
(``openai_compat``, ``deepl``, ``docling``, ...). Each adapter knows:

- which capabilities the protocol can serve (fixed list or "depends on probe")
- how to probe a concrete endpoint to confirm it works
- how to actually invoke the protocol-specific endpoints (when the protocol
  is not OpenAI-compatible and therefore needs custom request shaping)

The admin UI lists the registry of adapter classes as available "Protocols";
the database stores ``protocol`` as a free string keyed against that registry.
"""

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
    """Base class for every protocol adapter.

    Subclasses must set ``PROTOCOL`` and either ``FIXED_CAPABILITIES`` (for
    protocols where the capability set is implied by the spec, like DeepL or
    Docling) or leave it as ``None`` (for ``openai_compat`` where the actual
    capability set depends on what the configured server exposes).
    """

    PROTOCOL: str = ""
    FIXED_CAPABILITIES: Optional[tuple[str, ...]] = None

    def __init__(self, *, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @abstractmethod
    def probe(self) -> ProbeResult:
        """Run a probe against ``base_url`` and report capabilities + status."""
        ...
