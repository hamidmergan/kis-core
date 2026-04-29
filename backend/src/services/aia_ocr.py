"""OCR providers for KI Tutor – Vision-LLM based.

Both KISSKI and THL myLab expose OCR via their OpenAI-compatible
/v1/chat/completions endpoint using a Vision-LLM (e.g. nanonets-ocr2-3b on
myLab, qwen2.5-vl on KISSKI). Image input is passed as a base64 data URL.
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
    "word: NONE. Output plain text only — no markdown fences, no 'Here is' intro."
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


class KisskiOcrProvider(OcrProvider):
    """OCR via KISSKI Vision-LLM (academiccloud.de)."""

    def __init__(self) -> None:
        from langfuse.openai import OpenAI
        from src.config import Settings
        from src.services.runtime_models import get_model
        s = Settings()
        self._client = OpenAI(api_key=s.kisski_api_key, base_url=s.kisski_base_url)
        self._model = get_model("kisski_ocr_model")

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        return _call_vlm(self._client, self._model, image_bytes, mime_type)


class MyLabOcrProvider(OcrProvider):
    """OCR via THL myLab Vision-LLM (nanonets-ocr2-3b by default)."""

    def __init__(self) -> None:
        from langfuse.openai import OpenAI
        from src.config import Settings
        from src.services.runtime_models import get_model
        s = Settings()
        base = (s.mylab_base_url or "").rstrip("/")
        if not base:
            raise RuntimeError("MYLAB_BASE_URL nicht konfiguriert")
        self._client = OpenAI(api_key="ignored", base_url=f"{base}/v1")
        self._model = get_model("mylab_ocr_model")

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        return _call_vlm(self._client, self._model, image_bytes, mime_type)


def get_ocr_provider() -> Optional[OcrProvider]:
    """Return the currently-active OCR provider, or None if OCR is disabled.

    Priority (matches the admin UI label 'KISSKI = primär, THL myLab = Fallback'):
      1. kisski_ocr_enabled (default true)  → KisskiOcrProvider
      2. mylab_ocr_enabled  (default false) → MyLabOcrProvider (fallback)
      otherwise → None
    """
    from src import database as db
    if db.get_setting("kisski_ocr_enabled", "true").lower() == "true":
        try:
            return KisskiOcrProvider()
        except Exception as e:
            logger.warning("KISSKI OCR init failed: {}", e)
    if db.get_setting("mylab_ocr_enabled", "false").lower() == "true":
        try:
            return MyLabOcrProvider()
        except Exception as e:
            logger.warning("MyLab OCR init failed: {}", e)
    return None
