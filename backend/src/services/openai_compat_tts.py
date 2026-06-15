"""OpenAI-compatible TTS client.

Endpoints used (OpenAI Audio spec):
    POST /v1/audio/speech   -> audio bytes (mp3)
    GET  /v1/models         -> health probe

Works with any OpenAI-compatible TTS server. Voices are managed in the
providers.voices DB column, not hardcoded here.
"""
from __future__ import annotations

import httpx

_CHUNK_MAX = 10_000
_CHUNK_MIN = 9_500


def _split_text(text: str) -> list[str]:
    """Split long text at sentence boundaries."""
    if len(text) <= _CHUNK_MAX:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > _CHUNK_MAX:
        split_at = -1
        for punct in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
            pos = remaining.rfind(punct, _CHUNK_MIN, _CHUNK_MAX)
            if pos != -1:
                split_at = pos + len(punct)
                break
        if split_at == -1:
            split_at = _CHUNK_MAX
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
        language: str = "de",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> bytes:
        """Convert text to MP3 bytes."""
        chunks = _split_text(text)
        audio_parts: list[bytes] = []

        with httpx.Client(timeout=300.0) as client:
            for chunk in chunks:
                audio_parts.append(self._synthesize_one(client, chunk, voice_id=voice_id, speed=speed))

        return b"".join(audio_parts)

    def synthesize_chunk(
        self,
        text: str,
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        language: str = "de",
        **kwargs,
    ) -> bytes:
        """Synthesize a single chunk (for crash recovery in tts_tasks)."""
        with httpx.Client(timeout=300.0) as client:
            return self._synthesize_one(client, text, voice_id=voice_id, speed=speed)

    def _synthesize_one(
        self,
        client: httpx.Client,
        text: str,
        *,
        voice_id: str = "default",
        speed: float = 1.0,
    ) -> bytes:
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
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
        language: str = "de",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> dict:
        """Synthesize with optional alignment data.

        Returns {"audio_bytes": bytes, "alignment": None} — no timestamp support.
        """
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
