import pytest
from unittest.mock import MagicMock, patch


def test_synthesize_one_raises_on_default_voice_id():
    """voice_id='default' must raise, not silently use 'alloy'."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    client = OpenAICompatTTSClient("http://tts.example.com", model="kokoro")
    with pytest.raises(ValueError, match="voice_id must be set"):
        client._synthesize_one(MagicMock(), "hello", voice_id="default")


def test_synthesize_one_raises_on_empty_voice_id():
    """voice_id='' must raise, not silently use 'alloy'."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    client = OpenAICompatTTSClient("http://tts.example.com", model="kokoro")
    with pytest.raises(ValueError, match="voice_id must be set"):
        client._synthesize_one(MagicMock(), "hello", voice_id="")


def test_constructor_requires_model():
    """Constructing without model= must raise TypeError."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient
    with pytest.raises(TypeError):
        OpenAICompatTTSClient("http://tts.example.com")  # no model kwarg
