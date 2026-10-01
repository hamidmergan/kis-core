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


def test_synthesize_one_sends_no_speed():
    """A voice the provider slows down echoes, so no tempo ever goes out."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient

    client = OpenAICompatTTSClient("http://tts:8000", "xtts-v2")
    http = MagicMock()
    http.post.return_value = MagicMock(status_code=200, content=b"ID3")
    assert client._synthesize_one(http, "Hallo", voice_id="nova", speed=0.9) == b"ID3"
    payload = http.post.call_args.kwargs["json"]
    assert "speed" not in payload
    assert payload["voice"] == "nova"
