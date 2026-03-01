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
    if not settings.kisski_api_key:
        raise HTTPException(status_code=500, detail="KISSKI API Key nicht konfiguriert")
    return KisskiClient(
        api_key=settings.kisski_api_key,
        base_url=settings.kisski_base_url,
        model=settings.kisski_model,
    )


def get_elevenlabs_client() -> ElevenLabsClient:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=500, detail="ElevenLabs API Key nicht konfiguriert")
    return ElevenLabsClient(settings.elevenlabs_api_key)


def get_deepl_client():
    from src.services.deepl_client import DeepLClient
    settings = get_settings()
    if not settings.deepl_api_key:
        return None
    try:
        return DeepLClient(settings.deepl_api_key)
    except Exception:
        return None
