"""Adapter for Kokoro-FastAPI TTS endpoints.

Kokoro speaks the OpenAI audio/speech endpoint shape but ships a fixed
English voice catalogue exposed at ``/v1/audio/voices`` (not part of the
OpenAI spec). Treating Kokoro as its own protocol keeps the admin tab
honest (TTS-only capability, model name is irrelevant) and lets the
``KokoroClient`` keep its custom voice-list endpoint.
"""

from __future__ import annotations

import httpx
from loguru import logger

from src.services.protocols.base import ProbeResult, ProviderAdapter


class KokoroAdapter(ProviderAdapter):
    PROTOCOL = "kokoro"
    FIXED_CAPABILITIES = ("tts",)

    def _headers(self) -> dict:
        return {"Accept": "application/json"}

    def probe(self) -> ProbeResult:
        for path in ("/health", "/v1/audio/voices", "/"):
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get(f"{self.base_url}{path}", headers=self._headers())
                if resp.status_code < 500:
                    return ProbeResult(
                        capabilities=list(self.FIXED_CAPABILITIES),
                        status="ok",
                        error=None,
                    )
            except httpx.HTTPError as e:
                logger.debug("kokoro probe {}: {}", path, e)
                continue
        return ProbeResult(
            capabilities=[],
            status="error",
            error="unreachable",
        )
