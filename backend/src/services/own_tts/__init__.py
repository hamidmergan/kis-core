"""Outside voice services a person connects with their own account, at their own responsibility.

Each service has a fixed address and model here. A person only brings the key, never an address,
otherwise the server could be sent to ask machines inside the network.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

from src.i18n import t


@dataclass(frozen=True)
class Vendor:
    key: str
    label: str
    base_url: str
    model: str
    # Requests at once, the free plans allow only a few.
    concurrency: int
    module: ModuleType


def _vendors() -> dict[str, Vendor]:
    from src.services.own_tts import elevenlabs, fish_audio, gemini, openai_tts

    return {v.key: v for v in (
        # The free plan allows two requests at once with this model.
        Vendor("elevenlabs", elevenlabs.LABEL, elevenlabs.BASE_URL, elevenlabs.MODEL, 2, elevenlabs),
        # Google names no limit for the free tier, one at a time spares its caps per minute.
        Vendor("gemini", gemini.LABEL, gemini.BASE_URL, gemini.MODEL, 1, gemini),
        Vendor("fish", fish_audio.LABEL, fish_audio.BASE_URL, fish_audio.MODEL, 2, fish_audio),
        Vendor("openai", openai_tts.LABEL, openai_tts.BASE_URL, openai_tts.MODEL, 2, openai_tts),
    )}


VENDORS: dict[str, Vendor] = _vendors()


def is_own(provider: dict) -> bool:
    return provider.get("owner_user_id") is not None


def vendor_of(provider: dict) -> Vendor:
    return VENDORS[provider["protocol"]]


def model_for(provider: dict) -> str:
    return vendor_of(provider).model


def make_client(provider: dict, binding=None):
    """The voice client of an own interface, with a seat per request when a binding is given."""
    vendor = vendor_of(provider)
    return vendor.module.Client(provider.get("api_key") or "", vendor.model, binding)


def display_name(provider: dict, locale: str) -> str:
    """How a provider appears in a voice picker, an own interface marked as such."""
    if not is_own(provider):
        return provider["name"]
    return t("interfaces.ownProviderName", locale, vendor=vendor_of(provider).label)


def internal_name(vendor: Vendor, user_id: int) -> str:
    """The unique row name, it only shows up in the admin's technical details."""
    return f"{vendor.label} (eigener Zugang, Person {user_id})"
