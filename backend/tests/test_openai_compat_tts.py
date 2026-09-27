import pytest
from unittest.mock import MagicMock, patch


def test_synthesize_one_raises_on_default_voice_id():
    """voice_id='default' must raise, not silently use 'alloy'."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    client = OpenAICompatTTSClient("http://tts.example.com", model="stimme-v1")
    with pytest.raises(ValueError, match="voice_id must be set"):
        client._synthesize_one(MagicMock(), "hello", voice_id="default")


def test_synthesize_one_raises_on_empty_voice_id():
    """voice_id='' must raise, not silently use 'alloy'."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    client = OpenAICompatTTSClient("http://tts.example.com", model="stimme-v1")
    with pytest.raises(ValueError, match="voice_id must be set"):
        client._synthesize_one(MagicMock(), "hello", voice_id="")


def test_constructor_requires_model():
    """Constructing without model= must raise TypeError."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    with pytest.raises(TypeError):
        OpenAICompatTTSClient("http://tts.example.com")  # no model kwarg


def test_make_tts_client_raises_when_no_model():
    """make_tts_client must raise FeatureNotConfigured when binding has no model."""
    from src.services.feature_router import make_tts_client, FeatureBinding, FeatureNotConfigured
    binding = FeatureBinding(
        feature="tts",
        provider={"base_url": "http://tts.example.com", "name": "Stimmen lokal"},
        model=None,
    )
    with pytest.raises(FeatureNotConfigured, match="model_name"):
        make_tts_client(binding)


def test_openai_compat_llm_client_requires_whisper_model():
    """Constructing OpenAICompatLLMClient without whisper_model must raise TypeError."""
    from src.services.openai_compat_llm import OpenAICompatLLMClient
    with pytest.raises(TypeError):
        OpenAICompatLLMClient(
            api_key="k",
            base_url="http://example.com",
            model="gpt-4",
            provider="test",
            # whisper_model intentionally omitted
        )
