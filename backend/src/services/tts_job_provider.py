"""Chooses the voice provider once per job, the chosen one or the admin's fallback when it is down at the start.

A job never switches its provider afterwards, otherwise one podcast would speak with two voices.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from loguru import logger

from src import database as db


@dataclass(frozen=True)
class VoicePick:
    """The provider and voices a whole job runs with."""

    provider_id: int
    voices: tuple[str, ...]
    fallback: bool


def _marked_down(provider_id: int) -> bool:
    """Whether a failed call left a note on this provider's speech output a moment ago."""
    from src.services import provider_transport

    return provider_transport.is_down(provider_id, "tts")


def _reachable(provider: dict) -> bool:
    """A short probe, cached for a few seconds per process."""
    from src.dependencies import _tts_provider_reachable

    return _tts_provider_reachable(provider)


def _there(provider: dict | None) -> bool:
    return bool(provider and provider.get("enabled")) and not _marked_down(provider["id"]) and _reachable(provider)


def is_there(provider_id: int) -> bool:
    """Whether a job starting now would speak with this provider, seen exactly as pick sees it."""
    return _there(db.get_provider(provider_id))


def _usable_fallback(chosen_id: int) -> dict | None:
    """The admin's fallback for speech output, when it can take over a whole job right now."""
    route = db.get_route("tts") or {}
    fallback_id = route.get("fallback_provider_id")
    if not fallback_id or fallback_id == chosen_id:
        return None
    provider = db.get_provider(fallback_id)
    if not provider or provider.get("protocol") != "openai_compat" or "tts" not in (provider.get("capabilities") or []):
        return None
    if not (route.get("provider_models") or {}).get(str(fallback_id)) or not _voices(provider):
        return None
    return provider if _there(provider) else None


def _voices(provider: dict) -> list[dict]:
    """The voices a job can speak with, a voice without an id cannot be asked for."""
    return [v for v in provider.get("voices") or [] if v.get("voice_id")]


def _map_voices(chosen: dict | None, voice_ids: Sequence[str], fallback: dict,
                taken: Sequence[str] = ()) -> tuple[str, ...]:
    """The same voice when the fallback has it, else a free one in the same language, else the first free one."""
    sprache = {v.get("voice_id"): v.get("language", "") for v in (chosen or {}).get("voices") or []}
    angebot = _voices(fallback)
    zugeordnet: dict[str, str] = {}
    for vid in voice_ids:
        if vid in zugeordnet:
            continue
        besetzt = set(zugeordnet.values()) | set(taken)
        frei = [v for v in angebot if v.get("voice_id") not in besetzt] or angebot
        treffer = ([v for v in frei if v.get("voice_id") == vid]
                   or [v for v in frei if sprache.get(vid) and v.get("language") == sprache.get(vid)]
                   or frei)
        zugeordnet[vid] = treffer[0]["voice_id"]
    return tuple(zugeordnet[vid] for vid in voice_ids)


def pick(provider_id: int, voice_ids: Sequence[str], taken: Sequence[str] = ()) -> VoicePick:
    """Decides once at the start of a job, taken names fallback voices other speakers of the job already use."""
    chosen = db.get_provider(provider_id)
    # A person's own interface never hands over to the admin's fallback, the voice would change unasked.
    if _there(chosen) or (chosen or {}).get("owner_user_id") is not None:
        return VoicePick(provider_id, tuple(voice_ids), False)
    fallback = _usable_fallback(provider_id)
    if fallback is None:
        return VoicePick(provider_id, tuple(voice_ids), False)
    voices = _map_voices(chosen, voice_ids, fallback, taken)
    logger.warning("Stimmen: {} ist beim Start nicht da, der ganze Auftrag läuft mit {} ({})",
                   (chosen or {}).get("name") or provider_id, fallback.get("name"), ", ".join(voices))
    return VoicePick(fallback["id"], voices, True)


def voice_name(provider_id: int, voice_id: str) -> str:
    """The name a person sees for a voice of this provider, the id when the provider does not know it."""
    for v in (db.get_provider(provider_id) or {}).get("voices") or []:
        if v.get("voice_id") == voice_id:
            return v.get("name") or voice_id
    return voice_id
