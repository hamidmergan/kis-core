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

from src.config import Settings
from src.i18n import get_locale, t
from src.services import feature_router
from src.services.openai_compat_llm import OpenAICompatLLMClient


@lru_cache
def get_settings() -> Settings:
    return Settings()


async def get_current_user(request: Request) -> dict:
    """Return session data for the authenticated user.

    verify_auth already confirmed the session is valid, so this just
    reads the data. Falls back to defaults if something unexpected happens.
    """
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


def resolve_whisper_client() -> OpenAICompatLLMClient:
    """Resolve a Whisper client from the ``stt`` feature route.

    Lets ``FeatureNotConfigured`` propagate so Celery tasks can recognise
    the type and surface a localized error message instead of the internal
    English text.
    """
    binding = feature_router.resolve("stt")
    api_key, base_url, model, provider_name = _binding_tuple(binding)
    # Whisper model name lives in the feature_route's model_name slot. If
    # the admin left it blank, pick a sane default that matches the
    # historical fallback.
    whisper_model = model or "whisper-large-v2"
    return OpenAICompatLLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        provider=provider_name,
        whisper_model=whisper_model,
    )


def get_llm_client(locale: str = Depends(get_locale)) -> OpenAICompatLLMClient:
    try:
        api_key, base_url, model, provider = _resolve_llm_provider()
    except RuntimeError as e:
        logger.warning("LLM provider resolution failed: {}", e)
        raise HTTPException(status_code=503, detail=t("llm.notConfigured", locale))
    client = OpenAICompatLLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        provider=provider,
    )
    # Ollama defaults to a tiny num_ctx (4096) on its OpenAI-compat endpoint,
    # which silently truncates large RAG prompts (the citation rules at the
    # tail of the system prompt are the first things to disappear). Bump it
    # so the model actually sees the whole prompt + context. We detect
    # "looks-like-ollama" via the base_url since the provider name is now
    # admin-chosen and no longer a stable hint.
    if "11434" in base_url or "ollama" in base_url.lower():
        client._extra_body = {"options": {"num_ctx": 16384}}
    return client


# ─── TTS resolvers (kokoro / openai-compat TTS) ────────────────────────────

def _tts_providers_by_protocol(protocol: str) -> list[dict]:
    """Return enabled tts-routed providers matching ``protocol``."""
    matches: list[dict] = []
    for p in feature_router.providers_for_feature("tts"):
        if p.get("protocol") == protocol:
            matches.append(p)
    return matches


def _tts_model_for(provider_id: int, default: str) -> str:
    """Read the model_name out of the TTS feature_route, falling back to a default
    when the route is unset or the chosen provider doesn't match."""
    from src import database as db
    route = db.get_route("tts")
    if not route:
        return default
    if route.get("provider_id") == provider_id and route.get("model_name"):
        return route["model_name"] or default
    return default


def is_kokoro_enabled() -> bool:
    """True when at least one kokoro-protocol provider is wired into the TTS route."""
    return bool(_tts_providers_by_protocol("kokoro"))


def get_kokoro_client():
    """Instantiate a ``KokoroClient`` for the first kokoro provider on the TTS route."""
    from src.services.kokoro_client import KokoroClient
    candidates = _tts_providers_by_protocol("kokoro")
    if not candidates:
        return None
    return KokoroClient(candidates[0]["base_url"])


def is_mylab_enabled() -> bool:
    """True when at least one openai_compat TTS provider is wired into the TTS route.

    Name is historical — "myLab" used to be the only such provider; today this
    covers any OpenAI-compat speech endpoint the admin registered (XTTS-v2,
    openedai-speech, etc.).
    """
    return bool(_tts_providers_by_protocol("openai_compat"))


def get_mylab_client():
    """Instantiate the openai_compat TTS client for the first matching provider."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    candidates = _tts_providers_by_protocol("openai_compat")
    if not candidates:
        return None
    provider = candidates[0]
    model = _tts_model_for(provider["id"], default="xtts-v2")
    return OpenAICompatTTSClient(provider["base_url"], model=model)


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
