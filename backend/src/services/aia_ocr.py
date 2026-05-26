"""OCR providers for KI Tutor.

Two backends are supported, both selected at runtime via the admin panel:

- ``DoclingOcrProvider``: GWDG/KISSKI Docling-API. Per-image POST, dedicated
  document-understanding model. ~7s per typical slide vs. 30-70s for the
  vision-LLM route - 5-10x faster in practice.
- ``OpenAICompatOcrProvider``: OpenAI-compatible /v1/chat/completions with a
  Vision-LLM (e.g. THL myLab chandra-ocr-2). Kept as alternative provider.

Both expose the same ``ocr_image(bytes) -> str`` interface so the chunker
doesn't care which is active.
"""

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
        # Plain OpenAI client (not langfuse-wrapped): vision payloads trigger
        # Langfuse multimodal media uploads, which require an S3 bucket we
        # don't run. Tracing OCR calls isn't worth the operational cost.
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        return _call_vlm(self._client, self._model, image_bytes, mime_type)


class DoclingOcrProvider(OcrProvider):
    """OCR via GWDG/KISSKI Docling document-understanding API.

    Posts the image as a single-page document to ``/v1/documents/convert`` and
    returns the extracted markdown. The API runs IBM's Granite-Docling model
    end-to-end (layout + OCR) - much faster than a generic vision LLM, but the
    response is one markdown blob with no page metadata. Since the chunker
    calls this once per PDF page, page-mapping comes from the caller, not the
    response.
    """

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
        # Docling tags image-input responses with "<!-- image -->" and inlines
        # picture-N.png placeholders for embedded images. Neither belongs in
        # the chunk text - the rendered page is the source of truth visually.
        markdown = self._IMAGE_COMMENT_RE.sub("", markdown)
        markdown = self._PICTURE_REF_RE.sub("", markdown)
        return markdown.strip()


def get_ocr_provider() -> Optional[OcrProvider]:
    """Return the currently-active OCR provider, or None if OCR is unconfigured.

    Reads the ``ocr`` feature route from the admin tab. The chosen protocol
    determines the concrete client:
      - ``docling``: returns the ``DoclingAdapter`` (which carries an
        ``ocr_image`` method that matches the ``OcrProvider`` interface).
      - ``openai_compat``: returns an ``OpenAICompatOcrProvider`` driving a
        Vision-LLM via ``/v1/chat/completions``.
    """
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
