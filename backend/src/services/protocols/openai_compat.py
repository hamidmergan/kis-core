"""Adapter for any OpenAI-compatible HTTP endpoint.

Probe strategy — two-step fallback:

  1. ``GET /health`` — most OpenAI-compat servers expose a liveness probe.
     A 2xx response means the server is alive.

  2. ``GET /v1/models`` — fallback for servers without ``/health``. Any
     response except 404/5xx/401/403 confirms a live handler.

This avoids burning rate-limited capability endpoints. The admin can untick
capabilities the server doesn't serve via the Capabilities edit dialog.
"""

from __future__ import annotations

import httpx
from loguru import logger

from src.services.protocols.base import ProbeResult, ProviderAdapter


# Standard OpenAI-spec capabilities we assume a healthy server *might*
# implement. Includes "ocr" + "translation" because they piggyback on
# vision / chat respectively (see protocol README).
_DEFAULT_CAPABILITIES: tuple[str, ...] = (
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

_PROBE_TIMEOUT = 10.0


class OpenAICompatAdapter(ProviderAdapter):
    PROTOCOL = "openai_compat"
    FIXED_CAPABILITIES = None  # capabilities are probe-driven

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _base_host(self) -> str:
        """Return the bare host (no /v1 suffix) for health-check calls."""
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            return base[: -len("/v1")]
        return base

    def _build_url(self, path: str) -> str:
        """Combine ``base_url`` with a probe path that starts with ``/v1/``.

        Admins paste base URLs in two equally valid shapes — bare host
        (``https://api.example.com``) or already-with-``/v1`` suffix
        (``https://api.example.com/v1``). Without this helper the latter
        produces ``…/v1/v1/models`` which the upstream proxy rejects with
        an HTML 404.
        """
        base = self.base_url.rstrip("/")
        if base.endswith("/v1") and path.startswith("/v1/"):
            return base + path[len("/v1"):]
        return base + path

    def probe(self) -> ProbeResult:
        """Two-step reachability probe: GET /health then GET /v1/models.

        Step 1 — GET /health. A 2xx response is sufficient to declare the
        server alive.

        Step 2 — GET /v1/models fallback for servers without /health. Any
        response except 404 / 5xx / auth errors confirms a live OpenAI-compat
        handler.
        """
        with httpx.Client(timeout=_PROBE_TIMEOUT) as client:
            # Step 1: /health
            health_url = self._base_host() + "/health"
            try:
                r = client.get(health_url, headers=self._headers())
                logger.info("openai_compat probe: GET {} -> {}", health_url, r.status_code)
                if 200 <= r.status_code < 300:
                    return ProbeResult(capabilities=list(_DEFAULT_CAPABILITIES), status="ok", error=None)
            except httpx.HTTPError as e:
                logger.debug("openai_compat probe: /health unreachable ({}), trying /v1/models", e)

            # Step 2: /v1/models
            models_url = self._build_url("/v1/models")
            try:
                r = client.get(models_url, headers=self._headers())
            except httpx.HTTPError as e:
                logger.warning("openai_compat probe: GET {} unreachable: {}", models_url, e)
                return ProbeResult(
                    capabilities=[],
                    status="error",
                    error="unreachable",
                )

            status = r.status_code
            logger.info("openai_compat probe: GET {} -> {}", models_url, status)

            if status >= 500:
                return ProbeResult(
                    capabilities=[],
                    status="error",
                    error="server_error",
                )
            if status in (401, 403):
                return ProbeResult(
                    capabilities=[],
                    status="error",
                    error="auth_rejected",
                )
            if status == 404:
                return ProbeResult(
                    capabilities=[],
                    status="error",
                    error="endpoint_not_found",
                )

            # 2xx, 400, 405, 422 etc. all confirm a live OpenAI-compat handler.
            return ProbeResult(capabilities=list(_DEFAULT_CAPABILITIES), status="ok", error=None)
