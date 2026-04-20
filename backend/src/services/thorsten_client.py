"""Thorsten TTS client – Coqui TTS Server mit Thorsten-VITS Modell (deutsch).

Endpunkt:
    GET /api/tts?text=...  → WAV-Audio

Starten via Docker:
    docker-compose --profile thorsten up -d
"""
from __future__ import annotations

import httpx

DEFAULT_BASE_URL = "http://kis-thorsten:5002"

_CHUNK_MAX = 5_000
_CHUNK_MIN = 4_500


def _split_text(text: str) -> list[str]:
    """Teilt langen Text an Satzgrenzen auf."""
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


class ThorstenClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self._base_url = base_url.rstrip("/")

    def synthesize(
        self,
        text: str,
        language: str = "DE",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> bytes:
        """Wandelt Text in WAV-Bytes um."""
        chunks = _split_text(text)
        audio_parts: list[bytes] = []

        with httpx.Client(timeout=120.0) as client:
            for chunk in chunks:
                audio_parts.append(self._synthesize_one(client, chunk))

        return b"".join(audio_parts)

    def synthesize_chunk(
        self,
        text: str,
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> bytes:
        """Einzelnen Chunk synthetisieren."""
        with httpx.Client(timeout=120.0) as client:
            return self._synthesize_one(client, text)

    def _synthesize_one(self, client: httpx.Client, text: str) -> bytes:
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
        response = client.get(
            f"{self._base_url}/api/tts",
            params={"text": text},
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Thorsten TTS Fehler ({response.status_code}): {response.text[:300]}"
            )
        return response.content

    def get_voices(self) -> list[dict]:
        """Thorsten hat nur eine Stimme."""
        return [
            {"voice_id": "thorsten", "name": "Thorsten", "language": "Deutsch",
             "description": "Neutral, klar (CC0, Open Source)"},
        ]

    def synthesize_with_timestamps(
        self,
        text: str,
        language: str = "DE",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> dict:
        """Drop-in für ElevenLabsClient.synthesize_with_timestamps()."""
        audio_bytes = self.synthesize(text, language, voice_id=voice_id, speed=speed)
        return {"audio_bytes": audio_bytes, "alignment": None}

    def is_available(self) -> bool:
        """Prüft ob der Thorsten TTS Server erreichbar ist."""
        from loguru import logger
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self._base_url}/")
            logger.debug("Thorsten is_available: / -> HTTP {}", resp.status_code)
            return resp.status_code < 500
        except Exception as e:
            logger.warning("Thorsten is_available: {}: {}", type(e).__name__, e)
            return False
