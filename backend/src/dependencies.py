"""Shared FastAPI dependencies and thin wrappers around the feature router."""

from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, Request
from loguru import logger

from src import database as db
from src.config import Settings
from src.i18n import get_locale, t
from src.services import feature_router
from src.services.openai_compat_llm import OpenAICompatLLMClient


@lru_cache
def get_settings() -> Settings:
    return Settings()


async def get_current_user(request: Request) -> dict:
    """Session data of the logged-in user."""
    settings = get_settings()
    if settings.is_local_mode:
        from src import database as _db
        local_user = _db.get_user_by_username("local")
        if local_user:
            return {
                "user_id": local_user["id"],
                "username": "local",
                "display_name": "Admin",
                "email": "",
                "role": "admin",
                "custom_role_id": None,
            }

    token = request.cookies.get("session")
    if token:
        store = get_session_store()
        data = store.get_data(token)
        if data:
            return data
    return {"user_id": 0, "username": "unknown", "display_name": "Unknown"}


def is_admin_user(user: dict) -> bool:
    """Return True if the user is admin: env-admin OR has 'admin' role in session."""
    settings = get_settings()
    email = (user.get("email") or "").lower()
    if email and settings.admin_email and email == settings.admin_email.lower():
        return True
    return user.get("role") == "admin"


async def get_admin_user(request: Request, locale: str = Depends(get_locale)) -> dict:
    """Like get_current_user but raises 403 when the user is not an admin."""
    user = await get_current_user(request)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail=t("auth.adminRequired", locale))
    return user


@lru_cache
def get_session_store():
    from src.services.session import SessionStore

    settings = get_settings()
    return SessionStore(
        secret=settings.session_secret,
        max_age=86400,
    )


# ─── Legacy provider resolvers (now backed by feature_router) ──────────────

def _binding_tuple(binding: feature_router.FeatureBinding) -> tuple[str, str, str, str]:
    """Flattens a binding down to the old four-tuple."""
    p = binding.provider
    return (
        p.get("api_key") or "not-needed",
        feature_router._ensure_v1(p["base_url"]),
        binding.model or "",
        p["name"],
    )


def _resolve_llm_binding() -> feature_router.FeatureBinding:
    """Resolves the active chat binding, raises FeatureNotConfigured without a route."""
    return feature_router.resolve("chat")


def _resolve_llm_provider() -> tuple[str, str, str, str]:
    """Resolves the active chat model, raises FeatureNotConfigured without a route."""
    return _binding_tuple(_resolve_llm_binding())


def resolve_whisper_client(provider_id: Optional[int] = None) -> OpenAICompatLLMClient:
    """Resolves a Whisper credential, optionally via a chosen provider."""
    if provider_id is not None:
        from src.services import feature_provider_choices
        binding = feature_provider_choices.resolve_binding("stt", provider_id)
    else:
        binding = feature_router.resolve("stt")
    return feature_router.make_whisper_client(binding)


def get_llm_client(locale: str = Depends(get_locale)) -> OpenAICompatLLMClient:
    from src.services import provider_transport

    try:
        binding = _resolve_llm_binding()
    except RuntimeError as e:
        logger.warning("LLM provider resolution failed: {}", e)
        raise HTTPException(status_code=503, detail=t("llm.notConfigured", locale))
    api_key, base_url, model, provider = _binding_tuple(binding)
    return OpenAICompatLLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        whisper_model=model,
        provider=provider,
        **provider_transport.sdk_clients(binding),
    )


# ─── TTS resolvers ─────────────────────────────────────────────────────────

def get_tts_providers_with_voices(user: dict | None = None) -> list[dict]:
    """All enabled providers with speech output including their voices, then the person's own ones."""
    from src import database as db
    from src.services.own_tts.access import own_voice_providers
    providers = db.list_providers_with_capability("tts")
    shared = [p for p in providers if p.get("protocol") == "openai_compat"]
    return shared + (own_voice_providers(user) if user else [])


# Short-lived cache so a dead provider does not block every voice page.
_TTS_REACH_TTL_SEC = 30.0
_tts_reach_cache: dict[int, tuple[float, bool]] = {}


def _tts_provider_reachable(provider: dict) -> bool:
    """Briefly cached reachability probe of a speech output provider."""
    import time
    from src.services.openai_compat_tts import OpenAICompatTTSClient

    from src.services import own_tts

    pid = provider.get("id")
    now = time.monotonic()
    hit = _tts_reach_cache.get(pid)
    if hit and (now - hit[0]) < _TTS_REACH_TTL_SEC:
        return hit[1]
    if own_tts.is_own(provider):
        client = own_tts.make_client(provider)
    else:
        client = OpenAICompatTTSClient(
            provider["base_url"], model="", api_key=provider.get("api_key") or "not-needed"
        )
    ok = client.is_available()
    _tts_reach_cache[pid] = (now, ok)
    return ok


async def get_reachable_tts_providers_with_voices(user: dict | None = None) -> list[dict]:
    """Like get_tts_providers_with_voices but only currently reachable providers."""
    import asyncio

    providers = await asyncio.to_thread(get_tts_providers_with_voices, user)
    if not providers:
        return []
    loop = asyncio.get_running_loop()
    flags = await asyncio.gather(
        *(loop.run_in_executor(None, _tts_provider_reachable, p) for p in providers)
    )
    return [p for p, ok in zip(providers, flags) if ok]


def tts_model_for_provider(provider_id: int) -> str:
    """Which speech model sits behind this provider, or an empty string."""
    from src import database as db
    from src.services import own_tts
    provider = db.get_provider(provider_id)
    if provider and own_tts.is_own(provider):
        return own_tts.model_for(provider)
    route = db.get_route("tts")
    provider_models = (route.get("provider_models") if route else None) or {}
    return provider_models.get(str(provider_id)) or (route.get("model_name") if route else None) or ""


def get_tts_client_for_provider(provider_id: int, user_id: int | None = None):
    """The voice client for this provider, None when it is gone, off or someone else's own interface."""
    from src import database as db
    from src.services import own_tts
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    provider = db.get_provider(provider_id)
    if not provider or not provider.get("enabled"):
        return None
    if own_tts.is_own(provider):
        # Only the owner's own jobs speak with it, a caller without a person never does.
        if user_id is None or provider["owner_user_id"] != user_id:
            return None
        binding = feature_router.FeatureBinding(feature="tts", provider=provider, model=own_tts.model_for(provider))
        return own_tts.make_client(provider, binding)
    model = tts_model_for_provider(provider_id)
    if not model:
        raise feature_router.FeatureNotConfigured(
            "tts route has no model_name — set it in the admin KI panel"
        )
    api_key = provider.get("api_key") or "not-needed"
    binding = feature_router.FeatureBinding(feature="tts", provider=provider, model=model)
    return OpenAICompatTTSClient(provider["base_url"], model=model, api_key=api_key, binding=binding)


def _voice_language_for(provider_id: int, voice_id: str) -> str:
    """Looks up the language for a provider and voice pair, empty string otherwise."""
    from src import database as db
    provider = db.get_provider(provider_id)
    if not provider:
        return ""
    for v in provider.get("voices", []):
        if v.get("voice_id") == voice_id:
            return v.get("language", "")
    return ""


# ─── Translation resolvers ──────────────────────────────────────────────────

def get_translation_providers() -> list[dict]:
    """All enabled providers that can translate, the admin's first choice in front because callers take the first."""
    seen_ids: set[int] = set()
    result: list[dict] = []
    for cap in ("translation", "chat"):
        for p in db.list_providers_with_capability(cap):
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                result.append(p)
    first_id = (db.get_route("doc_translate") or {}).get("provider_id")
    return sorted(result, key=lambda p: p["id"] != first_id)


def get_translate_client_for_provider(
    provider_id: Optional[int], *, glossary_entries: dict | None = None, feature: str = "doc_translate"
):
    """Supplies the translation credential and terminology list for the TranslationService."""
    from src.services.glossary import GlossaryService

    if provider_id is None:
        # The admin's first choice for this feature, the first translating provider only without one.
        route = db.get_route(feature)
        provider_id = route.get("provider_id") if route else None
    if provider_id is None:
        providers = get_translation_providers()
        if not providers:
            return None, GlossaryService()
        provider_id = providers[0]["id"]

    provider = db.get_provider(provider_id)
    if not provider or not provider.get("enabled"):
        return None, GlossaryService()

    route = db.get_route(feature)
    provider_models = (route.get("provider_models") if route else None) or {}
    model = provider_models.get(str(provider_id)) or (route.get("model_name") if route else None) or ""
    provider_sampling = (route.get("provider_sampling") if route else None) or {}
    sampling = dict(provider_sampling.get(str(provider_id)) or {})

    glossary = GlossaryService()
    if provider.get("protocol") == "deepl":
        from src.services.deepl_client import DeepLClient
        if glossary_entries:
            glossary.set_entries(glossary_entries)
        return DeepLClient(provider.get("api_key") or ""), glossary
    else:
        from src.services import provider_transport
        from src.services.llm_translation_client import LLMTranslationClient
        base_url = feature_router._ensure_v1(provider["base_url"])
        if glossary_entries:
            glossary.set_entries(glossary_entries)
        binding = feature_router.FeatureBinding(feature=feature, provider=provider, model=model)
        client = LLMTranslationClient(
            api_key=provider.get("api_key") or "not-needed",
            base_url=base_url,
            model=model,
            provider=provider["name"],
            sampling=sampling,
            http_client=provider_transport.sdk_http_client(binding),
        )
        return client, glossary


# ─── DeepL resolvers ───────────────────────────────────────────────────────

def _deepl_provider() -> Optional[dict]:
    """First enabled DeepL provider on the doc_translate route."""
    for p in feature_router.providers_for_feature("doc_translate"):
        if p.get("protocol") == "deepl":
            return p
    return None


def resolve_deepl_api_key() -> str | None:
    """The active DeepL key, or None when no provider is set up."""
    provider = _deepl_provider()
    if not provider:
        return None
    return provider.get("api_key") or None


