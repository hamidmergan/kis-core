"""Resolves provider and model per feature and builds the finished client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src import database as db
from src.services.protocols import make_adapter


class FeatureNotConfigured(RuntimeError):
    """Raised when a feature has no provider, or the provider is disabled/gone."""


@dataclass
class FeatureBinding:
    """Resolved binding: which provider + model serves a feature, and how."""

    feature: str
    provider: dict
    model: Optional[str]
    # Temperatur und top_p aus dem Admin, leer heisst eingebauter Wert.
    sampling: dict = field(default_factory=dict)

    @property
    def protocol(self) -> str:
        return self.provider["protocol"]


# ─── Core resolver ─────────────────────────────────────────────────────────


def resolve(feature: str, *, user_provider_id: Optional[int] = None) -> FeatureBinding:
    """The binding for a feature, optionally with the user's choice."""
    route = db.get_route(feature)
    if route is None:
        raise FeatureNotConfigured(f"feature {feature!r} has no route")

    chosen_id: Optional[int]
    if user_provider_id is not None:
        allowed = route.get("user_choices") or []
        if user_provider_id not in allowed:
            raise FeatureNotConfigured(
                f"provider {user_provider_id} is not in user_choices for {feature!r}"
            )
        chosen_id = user_provider_id
    else:
        chosen_id = route.get("provider_id")

    if chosen_id is None:
        raise FeatureNotConfigured(f"feature {feature!r} has no provider assigned")

    provider = db.get_provider(chosen_id)
    if provider is None:
        raise FeatureNotConfigured(f"provider {chosen_id} (for {feature!r}) does not exist")
    if not provider.get("enabled"):
        raise FeatureNotConfigured(f"provider {chosen_id} ({provider['name']}) is disabled")

    provider_models = route.get("provider_models") or {}
    model = provider_models.get(str(chosen_id)) or route.get("model_name")
    provider_sampling = route.get("provider_sampling") or {}
    return FeatureBinding(
        feature=feature,
        provider=provider,
        model=model,
        sampling=dict(provider_sampling.get(str(chosen_id)) or {}),
    )


def is_configured(feature: str) -> bool:
    """Cheap check used by tool UIs / banners: would resolve() succeed?"""
    try:
        resolve(feature)
        return True
    except FeatureNotConfigured:
        return False


def providers_for_feature(feature: str) -> list[dict]:
    """The providers a tool may offer as a choice."""
    route = db.get_route(feature)
    if route is None:
        return []
    ids = route.get("user_choices") or []
    rows: list[dict] = []
    for pid in ids:
        row = db.get_provider(pid)
        if row and row.get("enabled"):
            rows.append(row)
    return rows


# The factories translate a binding into a finished client.


def make_llm_client(binding: FeatureBinding):
    """Return an OpenAICompatLLMClient for chat / embedding / vision / stt."""
    from src.services.openai_compat_llm import OpenAICompatLLMClient

    provider = binding.provider
    model = binding.model or ""
    client = OpenAICompatLLMClient(
        api_key=provider.get("api_key") or "not-needed",
        base_url=_ensure_v1(provider["base_url"]),
        model=model,
        whisper_model=model,
        provider=provider["name"],
    )
    client._sampling = dict(binding.sampling or {})
    _attach_model_profile(client, binding)
    return client


def _attach_model_profile(client, binding: FeatureBinding) -> None:
    """Attaches to the client what is known about its model."""
    from src.services import model_limits

    if binding.feature not in model_limits.CHAT_LIKE_FEATURES or not binding.model:
        return
    try:
        profil = model_limits.ensure_profile(binding.provider, binding.model)
    except Exception as e:  # noqa: BLE001 — ohne Profil laeuft alles wie vorher
        from loguru import logger
        logger.debug("Modellprofil nicht verfuegbar: {}", e)
        return
    client._model_profile = profil
    client._provider_id = binding.provider.get("id")
    zusatz = model_limits.think_off_body(profil)
    if zusatz:
        client._extra_body = {**(client._extra_body or {}), **zusatz}


def make_whisper_client(binding: FeatureBinding):
    """A client for speech recognition, the model is mandatory here."""
    if not binding.model:
        raise FeatureNotConfigured(
            f"stt provider '{binding.provider.get('name', '')}' has no model_name — "
            "set it in the admin KI panel"
        )
    return make_llm_client(binding)


def make_tts_client(binding: FeatureBinding):
    """Return an OpenAICompatTTSClient for the chosen TTS provider."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient

    if not binding.model:
        raise FeatureNotConfigured(
            f"tts provider '{binding.provider.get('name', '')}' has no model_name — "
            "set it in the admin KI panel"
        )
    provider = binding.provider
    return OpenAICompatTTSClient(
        base_url=provider["base_url"],
        model=binding.model,
        api_key=provider.get("api_key") or "not-needed",
    )


def make_ocr_provider(binding: FeatureBinding):
    """A text recognition provider matching the chosen protocol."""
    if binding.protocol == "docling":
        return make_adapter(
            protocol=binding.protocol,
            base_url=binding.provider["base_url"],
            api_key=binding.provider.get("api_key"),
        )
    if binding.protocol == "openai_compat":
        from src.services.aia_ocr import OpenAICompatOcrProvider

        return OpenAICompatOcrProvider(
            base_url=_ensure_v1(binding.provider["base_url"]),
            api_key=binding.provider.get("api_key") or "not-needed",
            model=binding.model or "",
            sampling=binding.sampling,
        )
    raise FeatureNotConfigured(
        f"OCR is not supported by protocol {binding.protocol!r}"
    )


# ─── Helpers ───────────────────────────────────────────────────────────────


def _ensure_v1(base_url: str) -> str:
    """Adds the missing /v1 to the address."""
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"
