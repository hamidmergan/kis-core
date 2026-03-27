from functools import lru_cache

from fastapi import HTTPException, Request

from src.config import Settings
from src.services.elevenlabs_client import ElevenLabsClient
from src.services.kisski_client import KisskiClient


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
    """Return True if the user is the configured admin."""
    settings = get_settings()
    email = user.get("email", "")
    return bool(email and email.lower() == settings.admin_email.lower())


async def get_admin_user(request: Request) -> dict:
    """Like get_current_user, but raises 403 if the user is not the admin."""
    user = await get_current_user(request)
    settings = get_settings()
    email = user.get("email", "")
    if not email or email.lower() != settings.admin_email.lower():
        raise HTTPException(status_code=403, detail="Admin-Zugriff erforderlich")
    return user


@lru_cache
def get_session_store():
    from src.services.session import SessionStore

    settings = get_settings()
    return SessionStore(
        secret=settings.session_secret,
        max_age=86400,
    )


def get_kisski_client() -> KisskiClient:
    settings = get_settings()
    if not settings.effective_llm_api_key:
        raise HTTPException(status_code=500, detail="KISSKI API Key nicht konfiguriert")
    return KisskiClient(
        api_key=settings.effective_llm_api_key,
        base_url=settings.effective_llm_base_url,
        model=settings.effective_llm_model,
        provider=settings.llm_provider,
    )


def get_elevenlabs_client() -> ElevenLabsClient:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=500, detail="ElevenLabs API Key nicht konfiguriert")
    return ElevenLabsClient(settings.elevenlabs_api_key)


def get_fish_speech_client():
    from src.services.fish_speech_client import FishSpeechClient
    settings = get_settings()
    if not settings.fish_speech_base_url:
        return None
    return FishSpeechClient(settings.fish_speech_base_url)


def get_kokoro_client():
    from src.services.kokoro_client import KokoroClient
    settings = get_settings()
    if not settings.kokoro_base_url:
        return None
    return KokoroClient(settings.kokoro_base_url, api_key=settings.kokoro_api_key)


def is_elevenlabs_enabled() -> bool:
    """Gibt True zurück wenn ElevenLabs konfiguriert UND vom Admin freigeschaltet."""
    from src import database as db
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        return False
    return db.get_setting("elevenlabs_enabled", "true").lower() == "true"


def is_kokoro_enabled() -> bool:
    """Gibt True zurück wenn Kokoro konfiguriert UND vom Admin freigeschaltet."""
    from src import database as db
    settings = get_settings()
    if not settings.kokoro_base_url:
        return False
    return db.get_setting("kokoro_enabled", "true").lower() == "true"


def get_thorsten_client():
    from src.services.thorsten_client import ThorstenClient
    settings = get_settings()
    if not settings.thorsten_base_url:
        return None
    return ThorstenClient(settings.thorsten_base_url)


def is_thorsten_enabled() -> bool:
    """Gibt True zurück wenn Thorsten TTS konfiguriert UND vom Admin freigeschaltet."""
    from src import database as db
    settings = get_settings()
    if not settings.thorsten_base_url:
        return False
    return db.get_setting("thorsten_enabled", "true").lower() == "true"


def get_mylab_client():
    from src.services.mylab_client import MyLabClient
    settings = get_settings()
    if not settings.mylab_tts_base_url:
        return None
    return MyLabClient(settings.mylab_tts_base_url, model=settings.mylab_tts_model)


def is_mylab_enabled() -> bool:
    """Gibt True zurück wenn myLab TTS konfiguriert UND vom Admin freigeschaltet."""
    from src import database as db
    settings = get_settings()
    if not settings.mylab_tts_base_url:
        return False
    return db.get_setting("mylab_enabled", "true").lower() == "true"


def get_deepl_client():
    from src.services.deepl_client import DeepLClient
    settings = get_settings()
    if not settings.deepl_api_key:
        return None
    try:
        return DeepLClient(settings.deepl_api_key)
    except Exception:
        return None
