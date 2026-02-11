from functools import lru_cache

from src.config import Settings


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
