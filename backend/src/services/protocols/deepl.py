"""Adapter for the DeepL translation API.

DeepL is a single-capability protocol: translation only. The probe is a real
translation of a tiny placeholder string so we can verify both the auth key
and the endpoint base URL in one request.
"""

from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger

from src.services.protocols.base import ProbeResult, ProviderAdapter


DEEPL_FREE_HOST = "https://api-free.deepl.com"
DEEPL_PRO_HOST = "https://api.deepl.com"


class DeepLAdapter(ProviderAdapter):
    PROTOCOL = "deepl"
    FIXED_CAPABILITIES = ("translation",)

    def _headers(self) -> dict:
        return {
            "Authorization": f"DeepL-Auth-Key {self.api_key or ''}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _effective_base_url(self) -> str:
        """Auto-route between DeepL's Free and Pro hosts based on the key suffix.

        Free keys end with ``:fx`` and only work on ``api-free.deepl.com``;
        Pro keys only work on ``api.deepl.com``. Only swap between these two
        canonical hosts - custom proxy URLs are left untouched.
        """
        if not self.api_key:
            return self.base_url
        canonical = self.base_url.rstrip("/")
        is_free_key = self.api_key.endswith(":fx")
        if is_free_key and canonical == DEEPL_PRO_HOST:
            return DEEPL_FREE_HOST
        if not is_free_key and canonical == DEEPL_FREE_HOST:
            return DEEPL_PRO_HOST
        return self.base_url

    def probe(self) -> ProbeResult:
        """Verify the configured key + URL by translating a probe string."""
        if not self.api_key:
            return ProbeResult(
                capabilities=[],
                status="error",
                error="DeepL requires an API key",
            )
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(
                    f"{self._effective_base_url()}/v2/translate",
                    headers=self._headers(),
                    data={"text": "probe", "target_lang": "EN"},
                )
        except httpx.HTTPError as e:
            logger.warning("DeepL probe failed for {}: {}", self.base_url, e)
            return ProbeResult(
                capabilities=[],
                status="error",
                error=f"unreachable: {type(e).__name__}: {e}",
            )

        if response.status_code == 200:
            return ProbeResult(capabilities=list(self.FIXED_CAPABILITIES), status="ok")
        if response.status_code in (401, 403):
            return ProbeResult(
                capabilities=[],
                status="error",
                error=f"auth rejected (HTTP {response.status_code})",
            )
        return ProbeResult(
            capabilities=[],
            status="error",
            error=f"unexpected HTTP {response.status_code}: {response.text[:200]}",
        )

    def translate(
        self,
        *,
        text: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> str:
        """Translate ``text`` to ``target_lang`` and return the translation."""
        data = {"text": text, "target_lang": target_lang.upper()}
        if source_lang:
            data["source_lang"] = source_lang.upper()
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self._effective_base_url()}/v2/translate",
                headers=self._headers(),
                data=data,
            )
        response.raise_for_status()
        payload = response.json()
        return payload["translations"][0]["text"]
