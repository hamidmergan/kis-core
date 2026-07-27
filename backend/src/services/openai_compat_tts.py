"""OpenAI-compatible TTS client.

Endpoints used (OpenAI Audio spec):
    POST /v1/audio/speech   -> audio bytes (mp3)
    GET  /v1/models         -> health probe

Works with any OpenAI-compatible TTS server. Voices are managed in the
providers.voices DB column, not hardcoded here.
"""
from __future__ import annotations

import httpx

from src.limits import TTS_MAX_CHARS_PER_REQUEST

# Ab welchem Anteil der Obergrenze nach einem Satzende gesucht wird. Darunter
# würden die Stücke unnötig kurz und die Zahl der Anfragen unnötig groß.
_SEARCH_FROM = 0.6

_SENTENCE_ENDS = (". ", "! ", "? ", ".\n", "!\n", "?\n")


def _resolve_chunk_limit() -> int:
    """Obergrenze je Anfrage, zur Laufzeit über die Admin-Einstellung änderbar.

    Die Grenze hängt am Anbieter, nicht am Text. Sie muss sich ohne neuen Build
    verschieben lassen, wenn ein anderer Anbieter mehr oder weniger verträgt.
    """
    try:
        from src import database as db
        value = int(db.get_setting("tts_max_chars_per_request", str(TTS_MAX_CHARS_PER_REQUEST)))
        return value if value > 0 else TTS_MAX_CHARS_PER_REQUEST
    except Exception:
        return TTS_MAX_CHARS_PER_REQUEST


def _split_text(text: str, max_chars: int | None = None) -> list[str]:
    """Langen Text in Stücke zerlegen, bevorzugt an Satzenden.

    Der Anbieter bricht nach einer festen Zeit ab, nicht nach einer festen
    Länge. Deshalb ist die Obergrenze bewusst klein: ein Screencast-Skript mit
    1800 Zeichen ging vorher als eine Anfrage raus und lief immer in den
    Timeout. Reihenfolge der Schnittstellen: Satzende, sonst Wortgrenze, sonst
    harter Schnitt. Ein harter Schnitt ist in der Aufnahme hörbar, aber immer
    noch besser als gar keine Aufnahme.
    """
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
            # Kein Satzende in Reichweite: an der letzten Wortgrenze trennen.
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
