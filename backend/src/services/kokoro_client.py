"""Kokoro TTS client – lokaler Server auf Port 8090.

Identische Signatur wie FishSpeechClient für Drop-in Kompatibilität.

Starten:
    conda activate kokoro
    python C:/Users/Hamid/Documents/kokoro-server/server.py
"""
from __future__ import annotations

import httpx

DEFAULT_BASE_URL = "http://localhost:8090"

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


class KokoroClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self._base_url = base_url.rstrip("/")

    def synthesize(
        self,
        text: str,
        language: str = "EN",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,  # ignorierte ElevenLabs-Parameter
    ) -> bytes:
        """Wandelt Text in MP3-Bytes um.

        Akzeptiert dieselbe Signatur wie ElevenLabsClient.synthesize() damit
        bestehende Aufrufer transparent umgestellt werden können.
        """
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
        **kwargs,  # ignorierte ElevenLabs-Parameter
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
        payload = {
            "text": text,
            "voice": voice_id,
            "speed": speed,
            "format": "mp3",
        }
        response = client.post(
            f"{self._base_url}/v1/tts",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Kokoro API Fehler ({response.status_code}): {response.text[:300]}"
            )
        return response.content

    # Feste Stimmliste für Kokoro v1.0 (Apache 2.0) — Server hat keinen /v1/voices Endpoint
    _BUILTIN_VOICES = [
        {"voice_id": "af_heart",    "name": "Heart",    "accent": "American", "gender": "Female"},
        {"voice_id": "af_alloy",    "name": "Alloy",    "accent": "American", "gender": "Female"},
        {"voice_id": "af_aoede",    "name": "Aoede",    "accent": "American", "gender": "Female"},
        {"voice_id": "af_bella",    "name": "Bella",    "accent": "American", "gender": "Female"},
        {"voice_id": "af_jessica",  "name": "Jessica",  "accent": "American", "gender": "Female"},
        {"voice_id": "af_kore",     "name": "Kore",     "accent": "American", "gender": "Female"},
        {"voice_id": "af_nicole",   "name": "Nicole",   "accent": "American", "gender": "Female"},
        {"voice_id": "af_nova",     "name": "Nova",     "accent": "American", "gender": "Female"},
        {"voice_id": "af_river",    "name": "River",    "accent": "American", "gender": "Female"},
        {"voice_id": "af_sarah",    "name": "Sarah",    "accent": "American", "gender": "Female"},
        {"voice_id": "af_sky",      "name": "Sky",      "accent": "American", "gender": "Female"},
        {"voice_id": "am_adam",     "name": "Adam",     "accent": "American", "gender": "Male"},
        {"voice_id": "am_echo",     "name": "Echo",     "accent": "American", "gender": "Male"},
        {"voice_id": "am_eric",     "name": "Eric",     "accent": "American", "gender": "Male"},
        {"voice_id": "am_fenrir",   "name": "Fenrir",   "accent": "American", "gender": "Male"},
        {"voice_id": "am_liam",     "name": "Liam",     "accent": "American", "gender": "Male"},
        {"voice_id": "am_michael",  "name": "Michael",  "accent": "American", "gender": "Male"},
        {"voice_id": "am_onyx",     "name": "Onyx",     "accent": "American", "gender": "Male"},
        {"voice_id": "am_puck",     "name": "Puck",     "accent": "American", "gender": "Male"},
        {"voice_id": "am_santa",    "name": "Santa",    "accent": "American", "gender": "Male"},
        {"voice_id": "bf_emma",     "name": "Emma",     "accent": "British",  "gender": "Female"},
        {"voice_id": "bf_isabella", "name": "Isabella", "accent": "British",  "gender": "Female"},
        {"voice_id": "bf_alice",    "name": "Alice",    "accent": "British",  "gender": "Female"},
        {"voice_id": "bf_lily",     "name": "Lily",     "accent": "British",  "gender": "Female"},
        {"voice_id": "bm_george",   "name": "George",   "accent": "British",  "gender": "Male"},
        {"voice_id": "bm_fable",    "name": "Fable",    "accent": "British",  "gender": "Male"},
        {"voice_id": "bm_lewis",    "name": "Lewis",    "accent": "British",  "gender": "Male"},
        {"voice_id": "bm_daniel",   "name": "Daniel",   "accent": "British",  "gender": "Male"},
    ]

    def get_voices(self) -> list[dict]:
        """Gibt alle verfügbaren Kokoro-Stimmen zurück.

        Versucht zuerst den Server-Endpoint /v1/voices. Falls dieser 404 liefert
        (Kokoro v1.0 hat keinen dynamischen Voices-Endpoint), wird die
        eingebettete Stimmliste zurückgegeben.
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self._base_url}/v1/voices")
            if resp.status_code == 200:
                data = resp.json().get("voices", [])
                if data:
                    return data
        except Exception:
            pass
        return self._BUILTIN_VOICES

    def synthesize_with_timestamps(
        self,
        text: str,
        language: str = "EN",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> dict:
        """Drop-in für ElevenLabsClient.synthesize_with_timestamps().

        Gibt {"audio_bytes": bytes, "alignment": None} zurück,
        da Kokoro keine Wort-Timestamps liefert.
        """
        audio_bytes = self.synthesize(text, language, voice_id=voice_id, speed=speed)
        return {"audio_bytes": audio_bytes, "alignment": None}

    def is_available(self) -> bool:
        """Prüft ob der lokale Kokoro Server erreichbar ist.

        Probiert GET /v1/voices (Primary), dann / und /health als Fallback.
        Loggt Fehler auf WARNING-Level damit sie in den Celery/FastAPI Logs sichtbar sind.
        """
        from loguru import logger
        for path in ("/v1/voices", "/health", "/"):
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get(f"{self._base_url}{path}")
                logger.debug("Kokoro is_available: {} -> HTTP {}", path, resp.status_code)
                if resp.status_code < 500:
                    return True
            except Exception as e:
                logger.warning("Kokoro is_available: {} -> {}: {}", path, type(e).__name__, e)
        return False
