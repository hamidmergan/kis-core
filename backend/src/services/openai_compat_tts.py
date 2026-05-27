"""OpenAI-compatible TTS client.

Endpoints used (OpenAI Audio spec):
    POST /v1/audio/speech   -> audio bytes (mp3)
    GET  /v1/models         -> health probe

Currently configured against TH Luebeck's myLab deployment of Coqui XTTS-v2
(``models.mylab.th-luebeck.dev``); any other openedai-speech / OpenAI-compat
TTS server with the same surface area works as a drop-in replacement.
"""
from __future__ import annotations

import httpx

_DEFAULT_VOICE = "alloy"
_DEFAULT_MODEL = "xtts-v2"

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


# Known voices of the OpenAI-compatible TTS API (openedai-speech).
# Each underlying voice is multilingual (XTTS-v2 auto-detects from input),
# so we expose every voice once per supported UI language. The "@<lang>"
# suffix is consumed by _synthesize_one before the request is sent upstream.
_SUPPORTED_LANGUAGES = ("de", "en")

_BASE_VOICES = [
    {"voice_id": "alloy",   "name": "Alloy",    "description": "Neutral, vielseitig"},
    {"voice_id": "echo",    "name": "Echo",     "description": "Warm, klar"},
    {"voice_id": "fable",   "name": "Fable",    "description": "Erzählerisch, ausdrucksstark"},
    {"voice_id": "onyx",    "name": "Onyx",     "description": "Tief, autoritär"},
    {"voice_id": "nova",    "name": "Nova",     "description": "Freundlich, energetisch"},
    {"voice_id": "shimmer", "name": "Shimmer",  "description": "Sanft, beruhigend"},
]


def _split_voice_language(voice_id: str) -> tuple[str, str | None]:
    """Strip an optional ``@<lang>`` suffix off a voice id."""
    if "@" in voice_id:
        base, lang = voice_id.rsplit("@", 1)
        if lang in _SUPPORTED_LANGUAGES:
            return base, lang
    return voice_id, None


_BUILTIN_VOICES = [
    {
        "voice_id": f"{v['voice_id']}@{lang}",
        "name": v["name"],
        "description": v["description"],
        "language": lang,
    }
    for v in _BASE_VOICES
    for lang in _SUPPORTED_LANGUAGES
]


class OpenAICompatTTSClient:
    """Client for any OpenAI-compatible TTS endpoint (POST /v1/audio/speech)."""

    def __init__(self, base_url: str, model: str = _DEFAULT_MODEL):
        # Providers store URLs with a trailing /v1 (the codebase convention).
        # We build every endpoint as {base_url}/v1/<path>, so strip the suffix
        # here to avoid the doubled /v1/v1/... that would otherwise result.
        url = base_url.rstrip("/")
        if url.endswith("/v1"):
            url = url[:-3]
        self._base_url = url
        self._model = model

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def synthesize(
        self,
        text: str,
        language: str = "DE",
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
        # Strip the internal ``@<lang>`` suffix - the upstream server only knows
        # the bare voice name. The language hint is purely UI metadata; XTTS-v2
        # auto-detects the spoken language from the input text itself.
        base_voice, _ = _split_voice_language(voice_id)
        voice = _DEFAULT_VOICE if base_voice in ("default", "") else base_voice
        payload: dict = {
            "model": self._model,
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "mp3",
        }
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

    def get_voices(self) -> list[dict]:
        """Return the available voices."""
        return list(_BUILTIN_VOICES)

    def synthesize_with_timestamps(
        self,
        text: str,
        language: str = "DE",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> dict:
        """Synthesize with optional alignment data.

        Returns {"audio_bytes": bytes, "alignment": None},
        since XTTS-v2 does not provide word timestamps.
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
