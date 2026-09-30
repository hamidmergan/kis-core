"""OpenAI: the same speech endpoint the platform's own providers use, only with the person's key."""
from __future__ import annotations

import httpx

from src.services.openai_compat_tts import OpenAICompatTTSClient
from src.services.own_tts._base import QUICK_TIMEOUT, OwnInterfaceError, UNREACHABLE, raise_for

LABEL = "OpenAI"
BASE_URL = "https://api.openai.com"
MODEL = "gpt-4o-mini-tts"
_QUOTA = ("insufficient_quota", "credit_balance_exhausted", "spend_limit_exceeded", "usage_limit_exceeded")

VOICES: tuple[str, ...] = (
    "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse",
    "marin", "cedar",
)


class Client(OpenAICompatTTSClient):
    """Turns the answers of OpenAI into the same refusals the other outside services give."""

    def __init__(self, api_key: str, model: str, binding=None):
        super().__init__(BASE_URL, model=model, api_key=api_key, binding=binding)

    def _synthesize_one(self, client, text, *, voice_id="default", speed=1.0, language=""):
        try:
            return super()._synthesize_one(client, text, voice_id=voice_id, speed=speed, language=language)
        except httpx.TransportError as e:
            raise OwnInterfaceError(UNREACHABLE, LABEL, str(e)) from e
        except RuntimeError as e:
            status = str(e).split("(", 1)[-1].split(")", 1)[0]
            fake = httpx.Response(int(status) if status.isdigit() else 500, text=str(e))
            raise_for(fake, LABEL, _QUOTA)
            raise


def list_voices(api_key: str) -> list[dict]:
    """The fixed voices, after the key has shown it is valid."""
    with httpx.Client(timeout=QUICK_TIMEOUT) as client:
        response = client.get(f"{BASE_URL}/v1/models", headers={"Authorization": f"Bearer {api_key}"})
    raise_for(response, LABEL, _QUOTA)
    return [{"voice_id": v, "name": v.capitalize(), "language": "", "description": ""} for v in VOICES]


def credit(api_key: str) -> dict | None:
    """OpenAI tells no balance for a key."""
    return None
