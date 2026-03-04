"""Kokoro TTS client – kompatibel mit Kokoro-FastAPI (ghcr.io/remsky/kokoro-fastapi-gpu).

Endpunkte (OpenAI-kompatibel):
    POST /v1/audio/speech   → Audio-Bytes (mp3)
    GET  /v1/voices         → Stimmliste

Auth: Authorization: Bearer <api_key>  (optional wenn kein Key gesetzt)

Starten via Docker:
    docker-compose --profile kokoro up -d
"""
from __future__ import annotations

import httpx

DEFAULT_BASE_URL = "http://kis-kokoro:8880"
_DEFAULT_VOICE = "af_heart"

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
    def __init__(self, base_url: str = DEFAULT_BASE_URL, api_key: str = ""):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def synthesize(
        self,
        text: str,
        language: str = "EN",
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
        # Normalize to single line — prevents phonemizer line-count mismatch.
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
        voice = _DEFAULT_VOICE if voice_id in ("default", "") else voice_id
        payload = {
            "model": "kokoro",
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "mp3",
            "stream": False,  # disable chunked streaming → single complete response
        }
        response = client.post(
            f"{self._base_url}/v1/audio/speech",
            json=payload,
            headers=self._headers(),
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Kokoro API Fehler ({response.status_code}): {response.text[:300]}"
            )
        return response.content

    # Feste Stimmliste als Fallback (Kokoro v1.0, Apache 2.0)
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

    _ENGLISH_PREFIXES = ("af_", "am_", "bf_", "bm_")

    @classmethod
    def _is_english(cls, voice_id: str) -> bool:
        return any(voice_id.startswith(p) for p in cls._ENGLISH_PREFIXES)

    @staticmethod
    def _normalize_voice_id(voice_id: str) -> dict:
        """Konvertiert z.B. 'af_alloy' → {voice_id, name='Alloy', accent='American', gender='Female'}."""
        accent = "British" if voice_id.startswith("b") else "American"
        gender = "Female" if len(voice_id) > 1 and voice_id[1] == "f" else "Male"
        name = voice_id[3:].replace("_", " ").title() if len(voice_id) > 3 else voice_id
        return {"voice_id": voice_id, "name": name, "accent": accent, "gender": gender}

    def get_voices(self) -> list[dict]:
        """Stimmliste vom Server abrufen, Fallback auf eingebettete Liste.
        Gibt nur englische Stimmen zurück (af_, am_, bf_, bm_).
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self._base_url}/v1/audio/voices", headers=self._headers())
            if resp.status_code == 200:
                data = resp.json()
                # Kokoro-FastAPI liefert {"voices": [...]} mit Strings oder Dicts
                voices_raw = data.get("voices") or data.get("data", [])
                if voices_raw:
                    normalized = []
                    for v in voices_raw:
                        if isinstance(v, str):
                            if self._is_english(v):
                                normalized.append(self._normalize_voice_id(v))
                        elif isinstance(v, dict):
                            vid = v.get("id") or v.get("voice_id", "")
                            if self._is_english(vid):
                                normalized.append(self._normalize_voice_id(vid))
                    if normalized:
                        return normalized
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
        """Prüft ob der Kokoro Server erreichbar ist."""
        from loguru import logger
        for path in ("/health", "/v1/audio/voices", "/"):
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get(f"{self._base_url}{path}", headers=self._headers())
                logger.debug("Kokoro is_available: {} -> HTTP {}", path, resp.status_code)
                if resp.status_code < 500:
                    return True
            except Exception as e:
                logger.warning("Kokoro is_available: {} -> {}: {}", path, type(e).__name__, e)
        return False
