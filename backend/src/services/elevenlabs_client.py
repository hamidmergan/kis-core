from __future__ import annotations

import re

import httpx

# English voice only
_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel – EN

_MODEL_ID = "eleven_multilingual_v2"
_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Optimized defaults for educational content
_DEFAULT_STABILITY = 0.70
_DEFAULT_SIMILARITY_BOOST = 0.60
_DEFAULT_STYLE = 0.20
_DEFAULT_SPEED = 0.90
_DEFAULT_SPEAKER_BOOST = True

# Pause presets: paragraph break durations only.
# ElevenLabs handles sentence pauses naturally — adding explicit
# sentence <break> tags causes progressive volume reduction.
PAUSE_PRESETS = {
    "short": 0.5,
    "medium": 1.0,
    "long": 2.0,
    "very_long": 3.0,
}


def _insert_pauses(text: str, pause_preset: str = "medium") -> str:
    """Insert <break> tags between paragraphs for natural pacing.

    A "paragraph boundary" is defined as two or more consecutive newlines.
    Sentence-level pauses are left to ElevenLabs' natural prosody.
    """
    pause_sec = PAUSE_PRESETS.get(pause_preset, PAUSE_PRESETS["medium"])

    if pause_sec <= 0:
        return text

    # Paragraph pauses (double newline)
    para_tag = f' <break time="{pause_sec:.1f}s" /> '
    text = re.sub(r"\n{2,}", para_tag, text)

    return text


class ElevenLabsClient:
    def __init__(self, api_key: str):
        self._api_key = api_key

    def synthesize(
        self,
        text: str,
        language: str,
        *,
        speed: float = _DEFAULT_SPEED,
        stability: float = _DEFAULT_STABILITY,
        similarity_boost: float = _DEFAULT_SIMILARITY_BOOST,
        style: float = _DEFAULT_STYLE,
        use_speaker_boost: bool = _DEFAULT_SPEAKER_BOOST,
        pause_preset: str = "medium",
    ) -> bytes:
        """Convert text to speech and return raw MP3 bytes.

        Args:
            text: The text to synthesize.
            language: 'EN' (only English supported).
            speed: Speech speed (0.7 – 1.2, default 0.9).
            stability: Voice stability (0 – 1, default 0.70).
            similarity_boost: Clarity / similarity (0 – 1, default 0.60).
            style: Style exaggeration (0 – 1, default 0.20).
            use_speaker_boost: Boost speaker similarity (default True).
            pause_preset: 'short', 'medium', 'long', or 'very_long'.

        Returns:
            MP3 audio bytes.

        Raises:
            ValueError: If params are invalid.
            RuntimeError: If the ElevenLabs API returns an error.
        """
        # Clamp values to valid ranges
        speed = max(0.5, min(1.2, speed))
        stability = max(0.0, min(1.0, stability))
        similarity_boost = max(0.0, min(1.0, similarity_boost))
        style = max(0.0, min(1.0, style))

        # Insert pauses
        processed_text = _insert_pauses(text, pause_preset)

        url = f"{_API_URL}/{_VOICE_ID}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload: dict = {
            "text": processed_text,
            "model_id": _MODEL_ID,
            "language_code": "en",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": use_speaker_boost,
            },
        }

        # speed != 1.0 → include in payload
        if abs(speed - 1.0) > 0.01:
            payload["speed"] = round(speed, 2)

        with httpx.Client(timeout=300.0) as client:
            response = client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", {})
                msg = detail.get("message", response.text) if isinstance(detail, dict) else str(detail)
            except Exception:
                msg = response.text
            raise RuntimeError(f"ElevenLabs API Fehler ({response.status_code}): {msg}")

        return response.content

    def synthesize_with_timestamps(self, text: str) -> dict:
        """Convert text to speech and return MP3 bytes with alignment data.

        Args:
            text: The text to synthesize.

        Returns:
            Dict with 'audio_bytes' (bytes) and 'alignment' (dict with
            characters, character_start_times_seconds, character_end_times_seconds).

        Raises:
            RuntimeError: If the ElevenLabs API returns an error.
        """
        url = f"{_API_URL}/{_VOICE_ID}/with-timestamps"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": _MODEL_ID,
            "language_code": "en",
            "voice_settings": {
                "stability": _DEFAULT_STABILITY,
                "similarity_boost": _DEFAULT_SIMILARITY_BOOST,
                "style": _DEFAULT_STYLE,
                "use_speaker_boost": _DEFAULT_SPEAKER_BOOST,
            },
        }

        with httpx.Client(timeout=300.0) as client:
            response = client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", {})
                msg = detail.get("message", response.text) if isinstance(detail, dict) else str(detail)
            except Exception:
                msg = response.text
            raise RuntimeError(f"ElevenLabs API Fehler ({response.status_code}): {msg}")

        data = response.json()

        import base64
        audio_bytes = base64.b64decode(data["audio_base64"])
        alignment = data.get("alignment", {})

        return {"audio_bytes": audio_bytes, "alignment": alignment}
