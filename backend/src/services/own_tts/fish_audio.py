"""Fish Audio: MP3 straight from the service, the person's own voices plus the best rated public ones."""
from __future__ import annotations

import httpx

from src.services.own_tts._base import QUICK_TIMEOUT, OwnTTSClient, raise_for

LABEL = "Fish Audio"
BASE_URL = "https://api.fish.audio"
# Free of charge without a card until 2026-11-30, after that the paid "s2.1-pro" takes its place.
MODEL = "s2.1-pro-free"
_SPEED_MIN, _SPEED_MAX = 0.5, 2.0
_QUOTA = ("insufficient credit", "insufficient balance")
# Public voices per language, the library holds thousands.
_PUBLIC_PER_LANGUAGE = {"de": 20, "en": 10}


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


class Client(OwnTTSClient):
    LABEL = LABEL

    def _speak(self, client: httpx.Client, text: str, voice_id: str, speed: float) -> bytes:
        response = client.post(
            f"{BASE_URL}/v1/tts",
            headers={**_headers(self._api_key), "model": self._model, "Content-Type": "application/json"},
            json={
                "text": text,
                "reference_id": voice_id,
                "format": "mp3",
                "mp3_bitrate": 128,
                "normalize": True,
                "prosody": {"speed": min(_SPEED_MAX, max(_SPEED_MIN, speed))},
            },
        )
        raise_for(response, LABEL, _QUOTA)
        return response.content

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{BASE_URL}/wallet/self/api-credit", headers=_headers(self._api_key))
            return response.status_code < 500
        except httpx.HTTPError:
            return False


def _models(client: httpx.Client, api_key: str, params: dict) -> list[dict]:
    response = client.get(f"{BASE_URL}/model", params={"page_number": 1, **params}, headers=_headers(api_key))
    raise_for(response, LABEL, _QUOTA)
    return [m for m in response.json().get("items") or [] if m.get("_id") and m.get("type", "tts") == "tts"]


def _voice(model: dict, own: bool) -> dict:
    sprachen = ", ".join(model.get("languages") or [])
    # Fish voices speak across languages, an empty language keeps them in every picker.
    return {"voice_id": model["_id"], "name": model.get("title") or model["_id"], "language": "",
            "description": "" if own else sprachen}


def list_voices(api_key: str) -> list[dict]:
    """The person's own voices first, then the best rated public German and English ones."""
    with httpx.Client(timeout=QUICK_TIMEOUT) as client:
        # Asked first because a wrong key fails here and not at the public library.
        response = client.get(f"{BASE_URL}/wallet/self/api-credit", headers=_headers(api_key))
        raise_for(response, LABEL, _QUOTA)
        eigene = _models(client, api_key, {"self": "true", "page_size": 100})
        oeffentlich = [m for sprache, anzahl in _PUBLIC_PER_LANGUAGE.items()
                       for m in _models(client, api_key, {"language": sprache, "sort_by": "score",
                                                          "page_size": anzahl})]
    gesehen: set[str] = set()
    stimmen = []
    for model, own in [(m, True) for m in eigene] + [(m, False) for m in oeffentlich]:
        if model["_id"] not in gesehen:
            gesehen.add(model["_id"])
            stimmen.append(_voice(model, own))
    return stimmen


def credit(api_key: str) -> dict | None:
    """Fish counts money, not characters, and the free model costs nothing."""
    return None
