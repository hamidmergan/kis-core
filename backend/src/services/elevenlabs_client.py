from __future__ import annotations

import re

import httpx

# Default voice
DEFAULT_VOICE_ID = "nPczCjzI2devNBz1zQrb"  # Brian – EN, deep, professional narration

# TTS model - alternatives:
# "eleven_turbo_v2_5"     -> Turbo, fast, slightly lower quality (currently used)
# "eleven_multilingual_v2" -> Highest quality, slower
# "eleven_flash_v2_5"     -> Fastest/cheapest model, noticeably lower quality
_MODEL_ID = "eleven_turbo_v2_5"
_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Turbo v2.5 allows max 30,000 chars per request - 5k chunks for minimal loss on crash
_CHUNK_SIZE = 5_000

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


_CHUNK_MIN = 4_800  # search window start
_CHUNK_MAX = 5_200  # hard cut if no sentence end found


def _split_text(text: str, max_chars: int = _CHUNK_SIZE) -> list[str]:
    """Split text into chunks that always end at a sentence boundary.

    Searches for a period (or ! ?) between _CHUNK_MIN and _CHUNK_MAX characters.
    Falls back to a hard cut at _CHUNK_MAX if no sentence end is found in that window.
    """
    if len(text) <= _CHUNK_MAX:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > _CHUNK_MAX:
        split_at = -1

        # Search for sentence end (. ! ?) between 4800 and 5200 chars
        for punct in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
            pos = remaining.rfind(punct, _CHUNK_MIN, _CHUNK_MAX)
            if pos != -1:
                split_at = pos + len(punct)
                break

        if split_at == -1:
            # No sentence end in window — hard cut at 5200
            split_at = _CHUNK_MAX

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    if remaining:
        chunks.append(remaining)

    return chunks


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
        voice_id: str = "",
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

        # Insert pauses then split into API-safe chunks
        processed_text = _insert_pauses(text, pause_preset)
        chunks = _split_text(processed_text)

        vid = voice_id or DEFAULT_VOICE_ID
        url = f"{_API_URL}/{vid}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        voice_settings = {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
        }

        audio_parts: list[bytes] = []
        prev_text = ""

        with httpx.Client(timeout=300.0) as client:
            for chunk in chunks:
                payload: dict = {
                    "text": chunk,
                    "model_id": _MODEL_ID,
                    "language_code": "en",
                    "voice_settings": voice_settings,
                }
                if abs(speed - 1.0) > 0.01:
                    payload["speed"] = round(speed, 2)
                if prev_text:
                    payload["previous_text"] = prev_text[-200:]

                response = client.post(url, json=payload, headers=headers)

                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", {})
                        msg = detail.get("message", response.text) if isinstance(detail, dict) else str(detail)
                    except Exception:
                        msg = response.text
                    raise RuntimeError(f"ElevenLabs API Fehler ({response.status_code}): {msg}")

                audio_parts.append(response.content)
                prev_text = chunk

        return b"".join(audio_parts)

    def synthesize_chunk(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = _DEFAULT_SPEED,
        stability: float = _DEFAULT_STABILITY,
        similarity_boost: float = _DEFAULT_SIMILARITY_BOOST,
        style: float = _DEFAULT_STYLE,
        use_speaker_boost: bool = _DEFAULT_SPEAKER_BOOST,
        previous_text: str = "",
    ) -> bytes:
        """Synthesize a single pre-processed text chunk via one API call.

        Unlike synthesize(), this method does NOT split long texts internally.
        Use this when the caller manages chunking and saves each chunk individually
        (e.g. for crash recovery). Network errors propagate to the caller.
        """
        speed = max(0.5, min(1.2, speed))
        stability = max(0.0, min(1.0, stability))
        similarity_boost = max(0.0, min(1.0, similarity_boost))
        style = max(0.0, min(1.0, style))

        vid = voice_id or DEFAULT_VOICE_ID
        url = f"{_API_URL}/{vid}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload: dict = {
            "text": text,
            "model_id": _MODEL_ID,
            "language_code": "en",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": use_speaker_boost,
            },
        }
        if abs(speed - 1.0) > 0.01:
            payload["speed"] = round(speed, 2)
        if previous_text:
            payload["previous_text"] = previous_text[-200:]

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

    def synthesize_with_timestamps(
        self,
        text: str,
        language: str = "EN",
        *,
        voice_id: str = "",
        speed: float = _DEFAULT_SPEED,
        stability: float = _DEFAULT_STABILITY,
        similarity_boost: float = _DEFAULT_SIMILARITY_BOOST,
        style: float = _DEFAULT_STYLE,
        use_speaker_boost: bool = _DEFAULT_SPEAKER_BOOST,
        pause_preset: str = "medium",
    ) -> dict:
        """Convert text to speech and return MP3 bytes with alignment data.

        Accepts the same parameters as ``synthesize()`` so callers can
        forward TTS settings transparently.

        Returns:
            Dict with 'audio_bytes' (bytes) and 'alignment' (dict with
            characters, character_start_times_seconds, character_end_times_seconds).

        Raises:
            RuntimeError: If the ElevenLabs API returns an error.
        """
        # Clamp values to valid ranges
        speed = max(0.5, min(1.2, speed))
        stability = max(0.0, min(1.0, stability))
        similarity_boost = max(0.0, min(1.0, similarity_boost))
        style = max(0.0, min(1.0, style))

        # Insert pauses
        processed_text = _insert_pauses(text, pause_preset)

        vid = voice_id or DEFAULT_VOICE_ID
        url = f"{_API_URL}/{vid}/with-timestamps"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
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

        data = response.json()

        import base64
        audio_bytes = base64.b64decode(data["audio_base64"])
        alignment = data.get("alignment", {})

        return {"audio_bytes": audio_bytes, "alignment": alignment}

    def transcribe_with_timestamps(
        self,
        file_bytes: bytes,
        filename: str,
        language_code: str = "en",
    ) -> dict:
        """Transcribe audio or video and return word-level timestamps.

        Uses ElevenLabs Speech-to-Text (Scribe v1) which accepts MP3, MP4
        and other audio/video formats up to 3 GB.

        Args:
            file_bytes: Raw bytes of the audio or video file.
            filename: Original filename with extension (e.g. 'dubbed.mp4').
            language_code: ISO 639-1 language hint (default 'en').

        Returns:
            Dict with:
              - 'words': list of {"word": str, "start": float, "end": float}
              - 'text': full plain-text transcript

        Raises:
            RuntimeError: If the ElevenLabs API returns an error.
        """
        import mimetypes
        mime, _ = mimetypes.guess_type(filename)
        if not mime:
            mime = "application/octet-stream"

        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {"xi-api-key": self._api_key}

        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                url,
                headers=headers,
                data={
                    "model_id": "scribe_v1",
                    "language_code": language_code,
                    "timestamps_granularity": "word",
                },
                files={"file": (filename, file_bytes, mime)},
            )

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", {})
                msg = detail.get("message", response.text) if isinstance(detail, dict) else str(detail)
            except Exception:
                msg = response.text
            raise RuntimeError(f"ElevenLabs STT Fehler ({response.status_code}): {msg}")

        data = response.json()

        # STT returns words as {"type": "word"|"spacing"|"audio_event", "text", "start", "end"}
        # Normalise to {"word": str, "start": float, "end": float} for subtitle_converter
        raw_words = data.get("words", [])
        words = [
            {"word": w["text"], "start": w["start"], "end": w["end"]}
            for w in raw_words
            if w.get("type") == "word"
        ]

        return {
            "words": words,
            "text": data.get("text", ""),
        }
