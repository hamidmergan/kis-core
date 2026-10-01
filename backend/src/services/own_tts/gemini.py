"""Gemini: a fixed set of voices, raw audio that becomes MP3 here."""
from __future__ import annotations

import base64

import httpx

from src.services.own_tts._base import (
    BILLING, KEY_INVALID, QUICK_TIMEOUT, OwnInterfaceError, OwnTTSClient, raise_for, to_mp3,
)

LABEL = "Gemini"
BASE_URL = "https://generativelanguage.googleapis.com"
# The stable speech model, free of charge in the free tier (as of 2026-09-30).
MODEL = "gemini-3.8-flash-tts"
# The service answers with a WAV of 16 bit mono at this rate, or without the header.
_RATE = 24000
# A daily cap stays for the day, a cap per minute passes and is worth another try.
_QUOTA = ("perday", "per day")
# Google answers a wrong key with 400, not 401.
_BAD_KEY = ("api_key_invalid", "api key not valid", "api key expired")

# The prebuilt voices with the character Google gives each, every one speaks all languages.
VOICES: tuple[tuple[str, str], ...] = (
    ("Zephyr", "Bright"), ("Puck", "Upbeat"), ("Charon", "Informative"), ("Kore", "Firm"),
    ("Fenrir", "Excitable"), ("Leda", "Youthful"), ("Orus", "Firm"), ("Aoede", "Breezy"),
    ("Callirrhoe", "Easy-going"), ("Autonoe", "Bright"), ("Enceladus", "Breathy"), ("Iapetus", "Clear"),
    ("Umbriel", "Easy-going"), ("Algieba", "Smooth"), ("Despina", "Smooth"), ("Erinome", "Clear"),
    ("Algenib", "Gravelly"), ("Rasalgethi", "Informative"), ("Laomedeia", "Upbeat"), ("Achernar", "Soft"),
    ("Alnilam", "Firm"), ("Schedar", "Even"), ("Gacrux", "Mature"), ("Pulcherrima", "Forward"),
    ("Achird", "Friendly"), ("Zubenelgenubi", "Casual"), ("Vindemiatrix", "Gentle"), ("Sadachbia", "Lively"),
    ("Sadaltager", "Knowledgeable"), ("Sulafat", "Warm"),
)


def _headers(api_key: str) -> dict:
    return {"x-goog-api-key": api_key, "Content-Type": "application/json"}


def _check(response: httpx.Response) -> None:
    text = response.text.lower()
    if response.status_code == 400 and any(m in text for m in _BAD_KEY):
        raise OwnInterfaceError(KEY_INVALID, LABEL, response.text[:500])
    if response.status_code == 400 and "failed_precondition" in text:
        raise OwnInterfaceError(BILLING, LABEL, response.text[:500])
    raise_for(response, LABEL, _QUOTA)


class Client(OwnTTSClient):
    LABEL = LABEL

    def _speak(self, client: httpx.Client, text: str, voice_id: str, speed: float) -> bytes:
        response = client.post(
            f"{BASE_URL}/v1beta/models/{self._model}:generateContent",
            headers=_headers(self._api_key),
            json={
                "contents": [{"parts": [{"text": text}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_id}}},
                },
            },
        )
        _check(response)
        try:
            data = response.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise RuntimeError(f"Gemini TTS without audio: {response.text[:300]}") from e
        # Never stretched, a slowed down voice echoes.
        return to_mp3(base64.b64decode(data), _RATE)

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{BASE_URL}/v1beta/models/{self._model}", headers=_headers(self._api_key))
            return response.status_code < 500
        except httpx.HTTPError:
            return False


def list_voices(api_key: str) -> list[dict]:
    """The fixed voices, after the key has shown it can reach the model."""
    with httpx.Client(timeout=QUICK_TIMEOUT) as client:
        response = client.get(f"{BASE_URL}/v1beta/models/{MODEL}", headers=_headers(api_key))
    _check(response)
    return [{"voice_id": name, "name": name, "language": "", "description": art} for name, art in VOICES]


def credit(api_key: str) -> dict | None:
    """Google tells no balance for a key."""
    return None
