from functools import lru_cache

from fastapi import HTTPException

from src.config import Settings
from src.services.elevenlabs_client import ElevenLabsClient
from src.services.kisski_client import KisskiClient


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_session_store():
    from src.services.session import SessionStore

    settings = get_settings()
    return SessionStore(
        secret=settings.session_secret,
        max_age=settings.session_max_age_seconds,
    )


def get_kisski_client() -> KisskiClient:
    settings = get_settings()
    if not settings.kisski_api_key:
        raise HTTPException(status_code=500, detail="KISSKI API Key fehlt")
    return KisskiClient(
        api_key=settings.kisski_api_key,
        base_url=settings.kisski_base_url,
        model=settings.kisski_model,
    )


def get_elevenlabs_client() -> ElevenLabsClient:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=500, detail="ElevenLabs API Key fehlt")
    return ElevenLabsClient(settings.elevenlabs_api_key)


@lru_cache
def get_deepl_client():
    from src.services.deepl_client import DeepLClient

    settings = get_settings()
    if not settings.deepl_api_key:
        return None
    try:
        return DeepLClient(settings.deepl_api_key)
    except Exception:
        return None
