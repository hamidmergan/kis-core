"""Shared FastAPI dependencies + legacy provider-resolver façade.

All client resolvers in this module are thin shims over
``src.services.feature_router``. Existing call-sites (chat, whisper, TTS,
deepl, ...) keep their public signatures so they don't need to be touched
individually. The router reads from the ``providers`` + ``feature_routes``
tables managed by the admin tab; legacy ``*_enabled`` settings rows are no
longer consulted anywhere.
"""

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
    """Return session data for the authenticated user.

    In local mode: always returns the local admin user from DB.
    """
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
    """Like get_current_user, but raises 403 if the user is not an admin.

    Kept for backwards compat with existing admin routes; equivalent in effect to
    require_admin from dependencies_rbac.
    """
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

def _ensure_v1(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"


def _binding_tuple(binding: feature_router.FeatureBinding) -> tuple[str, str, str, str]:
    """Flatten a binding into the (api_key, base_url, model, provider_name)
    tuple shape that the legacy resolvers used to return."""
    p = binding.provider
    return (
        p.get("api_key") or "not-needed",
        _ensure_v1(p["base_url"]),
        binding.model or "",
        p["name"],
    )


def _resolve_llm_provider() -> tuple[str, str, str, str]:
    """Resolve the active chat LLM. Raises ``FeatureNotConfigured`` (a
    ``RuntimeError`` subclass) when no chat route is set."""
    binding = feature_router.resolve("chat")
    return _binding_tuple(binding)


def _resolve_translation_llm_provider() -> tuple[str, str, str, str]:
    """LLM resolver used by ``/translate``. Prefers the doc_translate route;
    falls back to the chat route when doc_translate is unconfigured or
    points at a non-LLM protocol like DeepL."""
    try:
        binding = feature_router.resolve("doc_translate")
        if binding.protocol != "deepl":
            return _binding_tuple(binding)
    except feature_router.FeatureNotConfigured:
        pass
    return _resolve_llm_provider()


def resolve_whisper_client(provider_id: Optional[int] = None) -> OpenAICompatLLMClient:
    """Resolve a Whisper client for the ``stt`` feature.

    ``provider_id`` lets the end-user pick one of the STT providers the admin
    configured a model for (capability-based, same as the TTS picker); when
    omitted the admin default route is used. Lets ``FeatureNotConfigured``
    propagate so Celery tasks can surface a localized error message instead of
    the internal English text.
    """
    if provider_id is not None:
        from src.services import feature_provider_choices
        binding = feature_provider_choices.resolve_binding("stt", provider_id)
    else:
        binding = feature_router.resolve("stt")
    return feature_router.make_whisper_client(binding)


def get_llm_client(locale: str = Depends(get_locale)) -> OpenAICompatLLMClient:
    try:
        api_key, base_url, model, provider = _resolve_llm_provider()
    except RuntimeError as e:
        logger.warning("LLM provider resolution failed: {}", e)
        raise HTTPException(status_code=503, detail=t("llm.notConfigured", locale))
    return OpenAICompatLLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        whisper_model=model,
        provider=provider,
    )


# ─── TTS resolvers ─────────────────────────────────────────────────────────

def get_tts_providers_with_voices() -> list[dict]:
    """All enabled openai_compat providers that have the tts capability,
    including their voices list from the DB."""
    from src import database as db
    providers = db.list_providers_with_capability("tts")
    return [p for p in providers if p.get("protocol") == "openai_compat"]


def get_tts_client_for_provider(provider_id: int):
    """Return an OpenAICompatTTSClient for the given provider_id, or None."""
    from src import database as db
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    provider = db.get_provider(provider_id)
    if not provider or not provider.get("enabled"):
        return None
    route = db.get_route("tts")
    provider_models = (route.get("provider_models") if route else None) or {}
    model = provider_models.get(str(provider_id)) or (route.get("model_name") if route else None) or ""
    if not model:
        raise feature_router.FeatureNotConfigured(
            "tts route has no model_name — set it in the admin KI panel"
        )
    api_key = provider.get("api_key") or "not-needed"
    return OpenAICompatTTSClient(provider["base_url"], model=model, api_key=api_key)


def _voice_language_for(provider_id: int, voice_id: str) -> str:
    """Look up the language for a (provider_id, voice_id) pair from the DB voices list.

    Returns empty string if not found — callers should treat '' as 'unknown'.
    """
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
    """All enabled providers that can serve translation (translation or chat capability).

    DeepL providers have 'translation' capability; OpenAI-compat LLM providers
    have 'chat' and can translate via prompt. Returns a deduplicated list.
    """
    seen_ids: set[int] = set()
    result: list[dict] = []
    for cap in ("translation", "chat"):
        for p in db.list_providers_with_capability(cap):
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                result.append(p)
    return result


def get_translate_client_for_provider(
    provider_id: Optional[int], *, glossary_entries: dict | None = None, feature: str = "doc_translate"
):
    """Return (translation_client, GlossaryService) for use with TranslationService.

    When provider_id is None, falls back to the first available translation provider.
    Returns (None, GlossaryService()) if no provider can be found.

    ``feature`` is the route the per-provider model name is read from. It defaults to
    ``doc_translate`` (document tool) but transcript translation passes
    ``transcript_translate`` so its model can be configured independently.

    Protocol dispatch:
      deepl         -> DeepLClient + GlossaryService with entries
      openai_compat -> LLMTranslationClient (glossary passed in constructor)

    Note: for LLM providers the returned GlossaryService is intentionally empty;
    the glossary is embedded in the LLM system prompt instead.
    """
    from src.services.glossary import GlossaryService

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

    glossary = GlossaryService()
    if provider.get("protocol") == "deepl":
        from src.services.deepl_client import DeepLClient
        if glossary_entries:
            glossary.set_entries(glossary_entries)
        return DeepLClient(provider.get("api_key") or ""), glossary
    else:
        from src.services.llm_translation_client import LLMTranslationClient
        base_url = _ensure_v1(provider["base_url"])
        client = LLMTranslationClient(
            api_key=provider.get("api_key") or "not-needed",
            base_url=base_url,
            model=model,
            provider=provider["name"],
            glossary=glossary_entries or None,
        )
        return client, glossary


# ─── DeepL resolvers ───────────────────────────────────────────────────────

def _deepl_provider() -> Optional[dict]:
    """First enabled DeepL provider on the doc_translate route (or
    screencast_translate as a secondary lookup)."""
    for feature in ("doc_translate", "screencast_translate"):
        for p in feature_router.providers_for_feature(feature):
            if p.get("protocol") == "deepl":
                return p
    return None


def resolve_deepl_api_key() -> str | None:
    """Return the active DeepL API key, or None if no DeepL provider is configured.

    Historical .env fallback (``DEEPL_API_KEY``) is gone — the provider table
    is now the only source of truth, with the admin entering the key when they
    add a DeepL provider in the UI.
    """
    provider = _deepl_provider()
    if not provider:
        return None
    return provider.get("api_key") or None


def get_deepl_client():
    from src.services.deepl_client import DeepLClient
    api_key = resolve_deepl_api_key()
    if not api_key:
        return None
    try:
        return DeepLClient(api_key)
    except Exception as e:
        logger.warning("DeepL client init failed: {}", e)
        return None
