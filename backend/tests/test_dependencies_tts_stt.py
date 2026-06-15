import pytest
from unittest.mock import patch


def test_resolve_whisper_client_raises_when_no_model(monkeypatch):
    """resolve_whisper_client must raise FeatureNotConfigured when stt route has no model."""
    from src.services.feature_router import FeatureBinding, FeatureNotConfigured

    binding = FeatureBinding(
        feature="stt",
        provider={"base_url": "http://stt.example.com", "name": "Whisper", "api_key": None},
        model=None,
    )
    monkeypatch.setattr(
        "src.dependencies.feature_router.resolve",
        lambda f, *, user_provider_id=None: binding,
    )

    from src.dependencies import resolve_whisper_client
    with pytest.raises(FeatureNotConfigured, match="model_name"):
        resolve_whisper_client()


def test_get_tts_client_for_provider_raises_when_no_model(monkeypatch):
    """get_tts_client_for_provider must raise FeatureNotConfigured when no model is configured."""
    from src.services.feature_router import FeatureNotConfigured

    provider = {
        "id": 1,
        "name": "KokoroTTS",
        "protocol": "openai_compat",
        "base_url": "http://tts.example.com",
        "api_key": None,
        "enabled": True,
        "voices": [],
    }
    route = {"provider_models": {}, "model_name": None}

    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    monkeypatch.setattr("src.dependencies.db.get_route", lambda f: route)

    from src.dependencies import get_tts_client_for_provider
    with pytest.raises(FeatureNotConfigured, match="model_name"):
        get_tts_client_for_provider(1)
