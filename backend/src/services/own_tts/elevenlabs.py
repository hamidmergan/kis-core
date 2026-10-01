"""ElevenLabs: MP3 straight from the service, voices of the person's own library including clones."""
from __future__ import annotations

import httpx

from src.services.own_tts._base import QUICK_TIMEOUT, OwnTTSClient, raise_for

LABEL = "ElevenLabs"
BASE_URL = "https://api.elevenlabs.io"
# Speaks German well, one credit per character.
MODEL = "eleven_multilingual_v2"
_QUOTA = ("quota_exceeded", "insufficient_credits", "exceeds your quota")


def _headers(api_key: str) -> dict:
    return {"xi-api-key": api_key, "Content-Type": "application/json"}


class Client(OwnTTSClient):
    LABEL = LABEL

    def _speak(self, client: httpx.Client, text: str, voice_id: str, speed: float) -> bytes:
        response = client.post(
            f"{BASE_URL}/v1/text-to-speech/{voice_id}",
            params={"output_format": "mp3_44100_128"},
            headers=_headers(self._api_key),
            json={
                "text": text,
                # No tempo goes out, a voice slowed down by the provider echoes.
                "model_id": self._model,
            },
        )
        raise_for(response, LABEL, _QUOTA)
        return response.content

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{BASE_URL}/v2/voices", params={"page_size": 1},
                                      headers=_headers(self._api_key))
            return response.status_code < 500
        except httpx.HTTPError:
            return False


def _voice(entry: dict) -> dict:
    labels = entry.get("labels") or {}
    beschreibung = ", ".join(v for v in (labels.get("gender"), labels.get("accent"), labels.get("age")) if v)
    # Multilingual voices speak every language, an empty language keeps them in every picker.
    return {"voice_id": entry["voice_id"], "name": entry.get("name") or entry["voice_id"],
            "language": "", "description": beschreibung}


def list_voices(api_key: str) -> list[dict]:
    """Every voice of the account, the stock ones and the person's own, checks the key on the way."""
    voices: list[dict] = []
    token = None
    with httpx.Client(timeout=QUICK_TIMEOUT) as client:
        for _ in range(10):
            params = {"page_size": 100, **({"next_page_token": token} if token else {})}
            response = client.get(f"{BASE_URL}/v2/voices", params=params, headers=_headers(api_key))
            raise_for(response, LABEL, _QUOTA)
            data = response.json()
            voices += [_voice(v) for v in data.get("voices") or [] if v.get("voice_id")]
            token = data.get("next_page_token")
            if not data.get("has_more") or not token:
                break
    return voices


def credit(api_key: str) -> dict | None:
    """Characters used and allowed this month, None when the key may not read the plan."""
    with httpx.Client(timeout=QUICK_TIMEOUT) as client:
        response = client.get(f"{BASE_URL}/v1/user/subscription", headers=_headers(api_key))
    if response.status_code != 200:
        return None
    data = response.json()
    reset = data.get("next_character_count_reset_unix")
    from datetime import datetime, timezone
    return {
        "used": int(data.get("character_count") or 0),
        "limit": int(data.get("character_limit") or 0),
        "unit": "credits",
        "resets_at": datetime.fromtimestamp(reset, timezone.utc).isoformat() if reset else None,
    }
