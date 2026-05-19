from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from loguru import logger

from src.config import Settings
from src.i18n import get_locale, t
from src.services.elevenlabs_client import ElevenLabsClient
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


def _llm_provider_config(provider: str) -> tuple[str, str, str]:
    """Return (api_key, base_url, default_model) for a named provider.

    Raises RuntimeError if the provider is not configured (missing API key / base URL).
    Used by both `_resolve_llm_provider` (active provider) and the translation override.
    """
    settings = get_settings()
    from src.services.runtime_models import get_model

    if provider == "primary":
        if not settings.primary_provider_api_key:
            raise RuntimeError("Primary LLM not configured (PRIMARY_PROVIDER_API_KEY missing).")
        if not settings.primary_provider_base_url:
            raise RuntimeError("Primary LLM not configured (PRIMARY_PROVIDER_BASE_URL missing).")
        return settings.primary_provider_api_key, settings.primary_provider_base_url, get_model("primary_llm_model")
    if provider == "fallback":
        fallback_url = settings.fallback_provider_base_url or settings.mylab_tts_base_url
        if not fallback_url:
            raise RuntimeError("Secondary LLM not configured (SECONDARY_PROVIDER_BASE_URL missing).")
        return "ignored", f"{fallback_url.rstrip('/')}/v1", get_model("fallback_llm_model")
    if provider == "local":
        if not settings.local_provider_base_url:
            raise RuntimeError("Local LLM not configured (OLLAMA_BASE_URL missing).")
        return "ignored", settings.local_provider_base_url, get_model("local_llm_model")
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def _resolve_llm_provider() -> tuple[str, str, str, str]:
    """Resolve LLM provider based on admin toggles -> (api_key, base_url, model, provider_name).

    Exactly one provider may be active at a time (radio logic in routes/admin/settings.py).
    If none is active, raises RuntimeError with a clear instruction.
    """
    from src import database as db

    for key, name in (
        ("primary_llm_enabled", "primary"),
        ("fallback_llm_enabled", "fallback"),
        ("local_llm_enabled", "local"),
    ):
        if db.get_setting(key, "false").lower() == "true":
            api_key, base_url, model = _llm_provider_config(name)
            return api_key, base_url, model, name

    raise RuntimeError(
        "No LLM provider active. Enable exactly one in the admin panel under 'LLM Chat'."
    )


def _resolve_translation_llm_provider() -> tuple[str, str, str, str]:
    """Like _resolve_llm_provider, but with optional provider+model override for /translate.

    DB-backed (no env). Mirrors the LLM Chat pattern with per-provider model slots:
      - `translation_llm_provider`: "" | "primary" | "fallback" | "local"
      - `translation_primary_model`, `translation_fallback_model`, `translation_local_model`

    Empty provider → identical to _resolve_llm_provider.
    Set provider + empty per-provider model → that provider's default LLM model.
    Set provider + non-empty per-provider model → that exact model.
    """
    from src import database as db
    provider = db.get_setting("translation_llm_provider", "").strip()
    if not provider:
        return _resolve_llm_provider()

    from src.services.runtime_models import get_model
    api_key, base_url, _ = _llm_provider_config(provider)
    return api_key, base_url, get_model(f"translation_{provider}_model"), provider


def resolve_whisper_client() -> OpenAICompatLLMClient:
    """Resolve a Whisper client based on admin toggles.

    Whisper providers are a radio group: exactly one of
    ``primary_whisper_enabled`` / ``fallback_whisper_enabled`` is active.
    """
    from src import database as db
    settings = get_settings()

    from src.services.runtime_models import get_model

    if db.get_setting("fallback_whisper_enabled", "false").lower() == "true":
        secondary_url = settings.fallback_provider_base_url or settings.mylab_tts_base_url
        if not secondary_url:
            raise RuntimeError("Secondary Whisper enabled but SECONDARY_PROVIDER_BASE_URL not configured")
        return OpenAICompatLLMClient(
            api_key="not-needed",
            base_url=f"{secondary_url.rstrip('/')}/v1",
            model=get_model("fallback_llm_model"),
            provider="fallback",
            whisper_model="whisper-3-large",
        )
    if db.get_setting("primary_whisper_enabled", "true").lower() == "true":
        if not settings.primary_provider_api_key:
            raise RuntimeError("Primary Whisper enabled but PRIMARY_PROVIDER_API_KEY not configured")
        return OpenAICompatLLMClient(
            api_key=settings.primary_provider_api_key,
            base_url=settings.primary_provider_base_url,
            model=get_model("primary_llm_model"),
            provider="primary",
        )
    raise RuntimeError(
        "No Whisper provider active. Enable exactly one in the admin panel under 'Transcription'."
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
    # so the model actually sees the whole prompt + context.
    if provider == "local":
        client._extra_body = {"options": {"num_ctx": 16384}}
    return client


def get_elevenlabs_client(locale: str = Depends(get_locale)) -> ElevenLabsClient:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=500, detail=t("elevenlabs.notConfigured", locale))
    return ElevenLabsClient(settings.elevenlabs_api_key)


def get_kokoro_client():
    from src.services.kokoro_client import KokoroClient
    settings = get_settings()
    if not settings.kokoro_base_url:
        return None
    return KokoroClient(settings.kokoro_base_url)


def is_elevenlabs_enabled() -> bool:
    """Return True when ElevenLabs is configured AND enabled by the admin."""
    from src import database as db
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        return False
    return db.get_setting("elevenlabs_enabled", "true").lower() == "true"


def is_kokoro_enabled() -> bool:
    """Return True when Kokoro is configured AND enabled by the admin."""
    from src import database as db
    settings = get_settings()
    if not settings.kokoro_base_url:
        return False
    return db.get_setting("kokoro_enabled", "true").lower() == "true"


def get_mylab_client():
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    from src.services.runtime_models import get_model
    settings = get_settings()
    if not settings.mylab_tts_base_url:
        return None
    return OpenAICompatTTSClient(settings.mylab_tts_base_url, model=get_model("mylab_tts_model"))


def is_mylab_enabled() -> bool:
    """Return True when myLab TTS is configured AND enabled by the admin."""
    from src import database as db
    settings = get_settings()
    if not settings.mylab_tts_base_url:
        return False
    return db.get_setting("mylab_enabled", "true").lower() == "true"


def resolve_deepl_api_key() -> str | None:
    """Return the active DeepL API key, or None if nothing usable is configured.

    Admin override (settings.deepl_api_key_override) wins over the env var
    DEEPL_API_KEY. Empty / missing override -> env fallback.
    """
    from src import database as db
    override = db.get_setting("deepl_api_key_override", "").strip()
    if override:
        return override
    settings = get_settings()
    return settings.deepl_api_key or None


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
