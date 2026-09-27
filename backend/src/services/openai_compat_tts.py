"""Speech output via an OpenAI compatible endpoint, voices come from the database."""
from __future__ import annotations

from urllib.parse import urlparse

import httpx

from src.limits import TTS_MAX_CHARS_PER_REQUEST, TTS_PROVIDER_MAX_CONCURRENT, TTS_SLOT_WAIT_SECONDS
from src.services import provider_slots
from src.services.tts_number_words import spell_numbers

# From which share of the ceiling on a sentence end is looked for.
_SEARCH_FROM = 0.6

_SENTENCE_ENDS = (". ", "! ", "? ", ".\n", "!\n", "?\n")

# myLab gives up on a request after 60 s, so waiting five minutes only burns a slot.
_REQUEST_TIMEOUT = 90.0


def _resolve_chunk_limit() -> int:
    """Ceiling per request, changeable at runtime in the admin area."""
    try:
        from src import database as db
        value = int(db.get_setting("tts_max_chars_per_request", str(TTS_MAX_CHARS_PER_REQUEST)))
        return value if value > 0 else TTS_MAX_CHARS_PER_REQUEST
    except Exception:
        return TTS_MAX_CHARS_PER_REQUEST


def _split_text(text: str, max_chars: int | None = None) -> list[str]:
    """Splits long text, preferably at sentence ends, otherwise at word boundaries."""
    limit = max_chars or _resolve_chunk_limit()
    if len(text) <= limit:
        return [text]

    search_from = max(1, int(limit * _SEARCH_FROM))
    chunks: list[str] = []
    remaining = text

    while len(remaining) > limit:
        split_at = -1
        for punct in _SENTENCE_ENDS:
            pos = remaining.rfind(punct, search_from, limit)
            if pos != -1:
                split_at = pos + len(punct)
                break
        if split_at == -1:
            # No sentence end in reach: split at the last word boundary.
            pos = remaining.rfind(" ", search_from, limit)
            if pos != -1:
                split_at = pos + 1
        if split_at == -1:
            split_at = limit  # ein einzelnes Wort ist länger als die Grenze
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    if remaining:
        chunks.append(remaining)

    return chunks


class OpenAICompatTTSClient:
    """Client for any OpenAI-compatible TTS endpoint (POST /v1/audio/speech)."""

    def __init__(self, base_url: str, model: str, api_key: str = "not-needed"):
        url = base_url.rstrip("/")
        if url.endswith("/v1"):
            url = url[:-3]
        self._base_url = url
        self._model = model
        self._api_key = api_key or "not-needed"

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def synthesize(
        self,
        text: str,
        language: str = "",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> bytes:
        """Convert text to MP3 bytes."""
        chunks = _split_text(text)
        audio_parts: list[bytes] = []

        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            for chunk in chunks:
                audio_parts.append(
                    self._synthesize_one(client, chunk, voice_id=voice_id, speed=speed, language=language)
                )

        return b"".join(audio_parts)

    def synthesize_chunk(
        self,
        text: str,
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        language: str = "",
        **kwargs,
    ) -> bytes:
        """Synthesize a single chunk (for crash recovery in tts_tasks)."""
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            return self._synthesize_one(client, text, voice_id=voice_id, speed=speed, language=language)

    def _synthesize_one(
        self,
        client: httpx.Client,
        text: str,
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        language: str = "",
    ) -> bytes:
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
        # Digits would otherwise sound German, the voice guesses its language from the text.
        text = spell_numbers(text, language)
        if not voice_id or voice_id == "default":
            raise ValueError(
                "voice_id must be set — configure voices for this provider in the admin KI panel"
            )
        voice = voice_id
        payload: dict = {
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "mp3",
        }
        if self._model:
            payload["model"] = self._model
        # One seat per request, so all tools together never ask more than the provider manages.
        with provider_slots.slot(urlparse(self._base_url).netloc or self._base_url,
                                 limit=TTS_PROVIDER_MAX_CONCURRENT, wait_seconds=TTS_SLOT_WAIT_SECONDS):
            response = client.post(
                f"{self._base_url}/v1/audio/speech",
                json=payload,
                headers=self._headers(),
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"TTS API error ({response.status_code}): {response.text[:300]}"
            )
        return response.content

    def synthesize_with_timestamps(
        self,
        text: str,
        language: str = "",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> dict:
        """Generates audio, this provider does not support timestamps."""
        audio_bytes = self.synthesize(text, language, voice_id=voice_id, speed=speed)
        return {"audio_bytes": audio_bytes, "alignment": None}

    def is_available(self) -> bool:
        """Check if the TTS server is reachable (via /v1/models probe)."""
        from loguru import logger
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self._base_url}/v1/models", headers=self._headers())
            logger.debug("TTS is_available: {} /v1/models -> HTTP {}", self._base_url, resp.status_code)
            return resp.status_code < 500
        except Exception as e:
            logger.warning("TTS is_available probe failed: {}: {}", type(e).__name__, e)
            return False
