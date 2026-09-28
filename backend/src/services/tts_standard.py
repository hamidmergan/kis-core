"""The preselected voice of speech output: the starred provider with the admin's default voice."""

from __future__ import annotations

from typing import Optional

from src import database as db

_PROVIDER_KEY = "aia_flashcard_voice_provider_id"
_VOICE_KEY = "aia_flashcard_voice_id"


def star_id() -> Optional[int]:
    """The provider that carries the star in the admin's speech output row."""
    route = db.get_route("tts") or {}
    return route.get("provider_id")


def default_voice_setting() -> Optional[tuple[int, str]]:
    """The default voice from the admin area, as long as both halves are usable."""
    raw_provider = (db.get_setting(_PROVIDER_KEY, "") or "").strip()
    voice = (db.get_setting(_VOICE_KEY, "") or "").strip()
    if not raw_provider or not voice:
        return None
    try:
        provider_id = int(raw_provider)
    except ValueError:
        return None
    if provider_id < 1:
        return None
    return provider_id, voice


def star_first(providers: list[dict], lead_id: Optional[int]) -> list[dict]:
    """The providers with the leading one in front, the rest keep their order."""
    return sorted(providers, key=lambda p: p.get("id") != lead_id)


def _voice_ids(provider: dict) -> list[str]:
    return [vid for v in (provider.get("voices") or []) if (vid := (v.get("voice_id") or "").strip())]


def standard_voice(
    providers: list[dict],
    star: Optional[int],
    setting: Optional[tuple[int, str]],
) -> Optional[tuple[int, str]]:
    """The starred provider with the default voice when it is one of its own, otherwise its first voice."""
    ids = {p.get("id") for p in providers}
    # Without a usable star the provider of the default voice leads.
    lead = star if star in ids else (setting[0] if setting and setting[0] in ids else None)
    for provider in star_first(providers, lead):
        voices = _voice_ids(provider)
        if not voices:
            continue
        pid = int(provider["id"])
        if setting and setting[0] == pid and setting[1] in voices:
            return setting
        return pid, voices[0]
    return None
