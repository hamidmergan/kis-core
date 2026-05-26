"""Adapter for any OpenAI-compatible HTTP endpoint.

The probe used to POST one minimal request per capability endpoint, but:

  - It burned 7 requests per click against the admin's actual rate limit,
  - Many real OpenAI-compat servers (KISSKI/GWDG amongst them) do
    model-based routing that returns generic HTML 404 for unknown models
    instead of API-level 400, so "endpoint missing" was a lie half the time.

The probe now does **one** ``GET /v1/models`` call: if it succeeds we treat
the server as alive and seed the full set of standard capabilities. The
admin can then untick what the server doesn't actually serve via the
Capabilities edit dialog. This trades probe-precision for predictable cost
(1 request per click) and for honesty (no false negatives).
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

    def _build_url(self, path: str) -> str:
        """Combine ``base_url`` with a probe path that starts with ``/v1/``.

        Admins paste base URLs in two equally valid shapes — bare host
        (``https://api.example.com``) or already-with-``/v1`` suffix
        (``https://chat-ai.academiccloud.de/v1``). Without this helper the
        latter produces ``…/v1/v1/models`` which the upstream proxy rejects
        with an HTML 404.
        """
        base = self.base_url.rstrip("/")
        if base.endswith("/v1") and path.startswith("/v1/"):
            return base + path[len("/v1"):]
        return base + path

    def probe(self) -> ProbeResult:
        """Single reachability probe via ``GET /v1/models``.

        Success => server is alive => seed all standard capabilities and let
        the admin untick what doesn't actually work. Failure => return an
        ``error`` ProbeResult with the underlying HTTP / network reason.
        """
        url = self._build_url("/v1/models")
        try:
            with httpx.Client(timeout=_PROBE_TIMEOUT) as client:
                response = client.get(url, headers=self._headers())
        except httpx.HTTPError as e:
            logger.warning("openai_compat probe: GET {} unreachable: {}", url, e)
            return ProbeResult(
                capabilities=[],
                status="error",
                error=f"unreachable: {type(e).__name__}: {e}",
            )

        status = response.status_code
        logger.info("openai_compat probe: GET {} -> {}", url, status)

        if status >= 500:
            return ProbeResult(
                capabilities=[],
                status="error",
                error=f"server error on /v1/models: HTTP {status}",
            )
        if status in (401, 403):
            return ProbeResult(
                capabilities=[],
                status="error",
                error=f"auth rejected on /v1/models: HTTP {status}",
            )
        if status == 404:
            return ProbeResult(
                capabilities=[],
                status="error",
                error="GET /v1/models returned 404 — wrong base URL?",
            )

        # 2xx, 400, 405, 422 etc. all confirm a live OpenAI-compat handler.
        return ProbeResult(
            capabilities=list(_DEFAULT_CAPABILITIES),
            status="ok",
            error=None,
        )
