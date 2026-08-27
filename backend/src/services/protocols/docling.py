"""Adapter for the Docling API, one feature: text recognition."""

from __future__ import annotations

import re

import httpx
from loguru import logger

from src.services.protocols.base import ProbeResult, ProviderAdapter


_PICTURE_REF_RE = re.compile(r"^picture-\d+\.png\s*$", re.MULTILINE)
_IMAGE_COMMENT_RE = re.compile(r"<!--\s*image\s*-->")

# A tiny PNG as the probe payload.
_PROBE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class DoclingAdapter(ProviderAdapter):
    PROTOCOL = "docling"
    FIXED_CAPABILITIES = ("ocr",)

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def probe(self) -> ProbeResult:
        """POST a 1x1 PNG to verify the conversion endpoint accepts traffic."""
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    self.base_url,
                    headers=self._headers(),
                    files={"document": ("probe.png", _PROBE_PNG, "image/png")},
                )
        except httpx.HTTPError as e:
            logger.warning("Docling probe failed for {}: {}", self.base_url, e)
            return ProbeResult(
                capabilities=[],
                status="error",
                error="unreachable",
            )

        if response.status_code in (404, 405):
            return ProbeResult(
                capabilities=[],
                status="error",
                error="endpoint_not_found",
            )
        if response.status_code in (401, 403):
            return ProbeResult(
                capabilities=[],
                status="error",
                error="auth_rejected",
            )
        # 2xx / 400 / 422 all indicate the handler is reachable - probe ok.
        return ProbeResult(capabilities=list(self.FIXED_CAPABILITIES), status="ok")

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Send a single image to ``/documents/convert`` and return cleaned markdown."""
        ext = mime_type.rsplit("/", 1)[-1] or "png"
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                self.base_url,
                headers=self._headers(),
                files={"document": (f"page.{ext}", image_bytes, mime_type)},
            )
        response.raise_for_status()
        markdown = (response.json().get("markdown") or "").strip()
        markdown = _IMAGE_COMMENT_RE.sub("", markdown)
        markdown = _PICTURE_REF_RE.sub("", markdown)
        return markdown.strip()
