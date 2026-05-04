"""OCR providers for KI Tutor - Vision-LLM based.

OCR is delegated to an OpenAI-compatible /v1/chat/completions endpoint with a
Vision-LLM. The same adapter works against any OpenAI-compatible vision model;
the active deployment (model + base_url + key) is picked at runtime via the
admin panel. Image input is passed as a base64 data URL.
"""

import base64
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger


_OCR_SYSTEM_PROMPT = (
    "You are an OCR engine. Read ALL visible text in the image EXACTLY as it "
    "appears. Preserve line breaks, headings, lists, table structure (use | for "
    "columns), and formulas. Do NOT translate, summarize, rephrase, or add "
    "commentary. If the image contains no readable text, reply with the single "
    "word: NONE. Output plain text only - no markdown fences, no 'Here is' intro."
)


class OcrProvider(ABC):
    """Abstract base class for OCR providers."""

    @abstractmethod
    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Run OCR on an image. Returns extracted text (empty string on no-text)."""
        ...


def _call_vlm(client, model: str, image_bytes: bytes, mime_type: str) -> str:
    """Call an OpenAI-compatible Chat Completions endpoint with an image input."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "Transcribe all visible text."},
                ],
            },
        ],
        temperature=0.0,
        max_tokens=4000,
    )
    text = (response.choices[0].message.content or "").strip()
    if text.upper() == "NONE":
        return ""
    return text


class OpenAICompatOcrProvider(OcrProvider):
    """OCR via any OpenAI-compatible Vision-LLM endpoint.

    Multiple deployments (KISSKI, THL myLab, etc.) are different instances of
    this same class with their own ``base_url`` / ``api_key`` / ``model``.
    """

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        from langfuse.openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        return _call_vlm(self._client, self._model, image_bytes, mime_type)


# ── Per-provider factory functions ─────────────────────────────────────────

def _make_kisski_ocr_provider() -> OpenAICompatOcrProvider:
    """Build the KISSKI Vision-LLM OCR provider."""
    from src.config import Settings
    from src.services.runtime_models import get_model
    s = Settings()
    return OpenAICompatOcrProvider(
        base_url=s.primary_provider_base_url,
        api_key=s.primary_provider_api_key,
        model=get_model("primary_ocr_model"),
    )


def _make_mylab_ocr_provider() -> OpenAICompatOcrProvider:
    """Build the THL myLab Vision-LLM OCR provider."""
    from src.config import Settings
    from src.services.runtime_models import get_model
    s = Settings()
    base = (s.fallback_provider_base_url or "").rstrip("/")
    if not base:
        raise RuntimeError("myLab OCR base URL not configured")
    return OpenAICompatOcrProvider(
        base_url=f"{base}/v1",
        api_key="ignored",
        model=get_model("fallback_ocr_model"),
    )


def get_ocr_provider() -> Optional[OcrProvider]:
    """Return the currently-active OCR provider, or None if OCR is disabled.

    The admin panel exposes one toggle per provider; only one is expected to
    be active at a time. DB-key names (``primary_ocr_enabled`` /
    ``fallback_ocr_enabled``) are legacy and kept for backward compatibility.
    """
    from src import database as db
    if db.get_setting("primary_ocr_enabled", "true").lower() == "true":
        try:
            return _make_kisski_ocr_provider()
        except Exception as e:
            logger.warning("KISSKI OCR init failed: {}", e)
    if db.get_setting("fallback_ocr_enabled", "false").lower() == "true":
        try:
            return _make_mylab_ocr_provider()
        except Exception as e:
            logger.warning("myLab OCR init failed: {}", e)
    return None
