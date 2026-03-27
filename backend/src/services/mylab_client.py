"""myLab TTS client – OpenAI-kompatible API der TH Lübeck (Coqui XTTS-v2).

Endpunkte (OpenAI-kompatibel):
    POST /v1/audio/speech   → Audio-Bytes (mp3)

Base-URL: https://models.mylab.th-luebeck.dev
Modelle: tts-1-hd (= xtts-v2), xtts-v2

XTTS-v2 ist multilingual — unterstützt Deutsch, Englisch u.v.m.
Kein API-Key nötig (Campus-weit offen).
"""
from __future__ import annotations

import httpx

DEFAULT_BASE_URL = "https://models.mylab.th-luebeck.dev"
_DEFAULT_VOICE = "alloy"
_DEFAULT_MODEL = "tts-1-hd"

_CHUNK_MAX = 10_000
_CHUNK_MIN = 9_500


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


# Bekannte Stimmen der OpenAI-kompatiblen TTS-API (openedai-speech)
_BUILTIN_VOICES = [
    {"voice_id": "alloy",   "name": "Alloy",   "description": "Neutral, vielseitig"},
    {"voice_id": "echo",    "name": "Echo",     "description": "Warm, klar"},
    {"voice_id": "fable",   "name": "Fable",    "description": "Erzählerisch, ausdrucksstark"},
    {"voice_id": "onyx",    "name": "Onyx",     "description": "Tief, autoritär"},
    {"voice_id": "nova",    "name": "Nova",     "description": "Freundlich, energetisch"},
    {"voice_id": "shimmer", "name": "Shimmer",  "description": "Sanft, beruhigend"},
]


class MyLabClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, model: str = _DEFAULT_MODEL):
        self._base_url = base_url.rstrip("/")
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
        """Wandelt Text in MP3-Bytes um."""
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
        """Einzelnen Chunk synthetisieren (für Crash-Recovery in tts_tasks)."""
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
        voice = _DEFAULT_VOICE if voice_id in ("default", "") else voice_id
        payload = {
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
                f"myLab TTS API Fehler ({response.status_code}): {response.text[:300]}"
            )
        return response.content

    def get_voices(self) -> list[dict]:
        """Gibt die verfügbaren Stimmen zurück."""
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
        """Drop-in für ElevenLabsClient.synthesize_with_timestamps().

        Gibt {"audio_bytes": bytes, "alignment": None} zurück,
        da XTTS-v2 keine Wort-Timestamps liefert.
        """
        audio_bytes = self.synthesize(text, language, voice_id=voice_id, speed=speed)
        return {"audio_bytes": audio_bytes, "alignment": None}

    def is_available(self) -> bool:
        """Prüft ob der myLab TTS Server erreichbar ist."""
        from loguru import logger
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self._base_url}/v1/models", headers=self._headers())
            logger.debug("myLab TTS is_available: /v1/models -> HTTP {}", resp.status_code)
            return resp.status_code < 500
        except Exception as e:
            logger.warning("myLab TTS is_available: {}: {}", type(e).__name__, e)
            return False
