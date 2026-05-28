"""Runtime feature-routing.

Given a feature id (``chat`` / ``embedding`` / ``ocr`` / ...), resolve which
provider + model the admin selected, and produce a ready-to-use client. The
factories below intentionally return the existing legacy client classes
(``OpenAICompatLLMClient`` etc.) so the rest of the code base does not need
to switch all at once - the router is the only piece that knows about
``providers`` and ``feature_routes`` tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger

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

    @property
    def protocol(self) -> str:
        return self.provider["protocol"]


# ─── Core resolver ─────────────────────────────────────────────────────────


def resolve(feature: str, *, user_provider_id: Optional[int] = None) -> FeatureBinding:
    """Return the binding for ``feature``.

    For multi-pill features (``tts``, ``doc_translate``, ``screencast_translate``)
    the caller can pass ``user_provider_id`` to use the user's runtime choice
    instead of the admin's default; the chosen id must appear in the route's
    ``user_choices`` list.
    """
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
    return FeatureBinding(
        feature=feature,
        provider=provider,
        model=model,
    )


def is_configured(feature: str) -> bool:
    """Cheap check used by tool UIs / banners: would resolve() succeed?"""
    try:
        resolve(feature)
        return True
    except FeatureNotConfigured:
        return False


def providers_for_feature(feature: str) -> list[dict]:
    """List of providers a tool may offer as runtime picks for a multi-pill
    feature. Returns the user_choices entries with their full provider rows."""
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


# ─── Client factories ──────────────────────────────────────────────────────
# These match the surface of the legacy resolver functions in dependencies.py.
# They translate a FeatureBinding into a concrete client instance.


def make_llm_client(binding: FeatureBinding):
    """Return an OpenAICompatLLMClient for chat / embedding / vision / stt."""
    from src.services.openai_compat_llm import OpenAICompatLLMClient

    provider = binding.provider
    model = binding.model or ""
    return OpenAICompatLLMClient(
        api_key=provider.get("api_key") or "not-needed",
        base_url=_ensure_v1(provider["base_url"]),
        model=model,
        whisper_model=model,
        provider=provider["name"],
    )


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
    """Return an OCR provider that matches the chosen protocol.

    Docling protocol -> the adapter itself (it has an ``ocr_image`` method).
    OpenAI-compatible protocol -> the legacy ``OpenAICompatOcrProvider`` which
    drives a vision-LLM via ``/v1/chat/completions``.
    """
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
        )
    raise FeatureNotConfigured(
        f"OCR is not supported by protocol {binding.protocol!r}"
    )


def make_translation_adapter(binding: FeatureBinding):
    """For DeepL bindings, return the DeepL adapter. For LLM-based bindings,
    return the LLM client - the caller is responsible for prompt-driven
    translation in that case."""
    if binding.protocol == "deepl":
        return make_adapter(
            protocol="deepl",
            base_url=binding.provider["base_url"],
            api_key=binding.provider.get("api_key"),
        )
    return make_llm_client(binding)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _ensure_v1(base_url: str) -> str:
    """Some admins paste the bare host, others paste the ``/v1`` URL. Existing
    clients expect ``/v1`` already in the base. Add it if missing."""
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"
