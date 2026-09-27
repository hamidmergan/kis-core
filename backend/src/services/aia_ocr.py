"""Two text recognition providers with the same interface, chosen in the admin area."""

import base64
import re
from abc import ABC, abstractmethod
from typing import Optional

import httpx
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


def _call_vlm(client, model: str, image_bytes: bytes, mime_type: str,
              sampling: dict | None = None) -> str:
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
        **(dict(sampling) if sampling else {"temperature": 0.0}),
        max_tokens=4000,
    )
    text = (response.choices[0].message.content or "").strip()
    if text.upper() == "NONE":
        return ""
    return text


class OpenAICompatOcrProvider(OcrProvider):
    """Text recognition via an OpenAI compatible image endpoint."""

    def __init__(self, base_url: str, api_key: str, model: str,
                 sampling: dict | None = None, http_client=None) -> None:
        # A plain client without tracing, image data would need a bucket.
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        self._model = model
        # Abtastwerte aus dem Admin, leer heisst der eingebaute Wert gilt.
        self._sampling = dict(sampling or {})

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        return _call_vlm(self._client, self._model, image_bytes, mime_type, self._sampling)


class DoclingOcrProvider(OcrProvider):
    """Text recognition via the Docling API, much faster than an image model."""

    _PICTURE_REF_RE = re.compile(r"^picture-\d+\.png\s*$", re.MULTILINE)
    _IMAGE_COMMENT_RE = re.compile(r"<!--\s*image\s*-->")

    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/documents/convert"
        self._api_key = api_key
        self._timeout = timeout

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        ext = mime_type.rsplit("/", 1)[-1] or "png"
        files = {"document": (f"page.{ext}", image_bytes, mime_type)}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(self._endpoint, files=files, headers=headers)
        response.raise_for_status()
        markdown = (response.json().get("markdown") or "").strip()
        # Docling image placeholders do not belong in the chunk text.
        markdown = self._IMAGE_COMMENT_RE.sub("", markdown)
        markdown = self._PICTURE_REF_RE.sub("", markdown)
        return markdown.strip()


def get_ocr_provider() -> Optional[OcrProvider]:
    """The active text recognition provider, None when it is off or unconfigured."""
    from src import database as db
    if db.get_setting("ocr_enabled", "true").lower() != "true":
        logger.info("OCR resolver: globally disabled via admin setting, skipping OCR")
        return None
    from src.services import feature_router
    try:
        binding = feature_router.resolve("ocr")
    except feature_router.FeatureNotConfigured as e:
        logger.warning("OCR resolver: {}", e)
        return None
    try:
        return feature_router.make_ocr_provider(binding)
    except Exception as e:
        logger.warning("OCR provider init failed: {}", e)
        return None
