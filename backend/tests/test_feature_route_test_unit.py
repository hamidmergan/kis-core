"""Unit tests for feature_route_test — specifically the TTS path changes."""
import pytest
from unittest.mock import patch, MagicMock
from src.services.feature_route_test import FeatureTestResult


def test_tts_test_returns_error_when_no_model():
    """test_feature_route for TTS with model_name=None must return model_name_not_set."""
    from src.services.feature_route_test import test_feature_route

    result = test_feature_route(
        feature="tts",
        protocol="openai_compat",
        base_url="http://tts.example.com",
        api_key=None,
        model_name=None,
        voices=[{"voice_id": "af_bella", "name": "Bella"}],
    )
    assert result.status == "error"
    assert result.error == "model_name_not_set"


def test_tts_test_returns_error_when_no_voices():
    """test_feature_route for TTS with empty voices must return no_voices_configured."""
    from src.services.feature_route_test import test_feature_route

    result = test_feature_route(
        feature="tts",
        protocol="openai_compat",
        base_url="http://tts.example.com",
        api_key=None,
        model_name="kokoro",
        voices=[],
    )
    assert result.status == "error"
    assert result.error == "no_voices_configured"


def test_tts_test_uses_first_voice_from_db(monkeypatch):
    """_post_tts must use voices[0]['voice_id'] — not the hardcoded 'alloy'."""
    from src.services.feature_route_test import test_feature_route
    import httpx

    captured = {}

    def fake_post(self, url, **kwargs):
        captured["payload"] = kwargs.get("json", {})
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    test_feature_route(
        feature="tts",
        protocol="openai_compat",
        base_url="http://tts.example.com",
        api_key=None,
        model_name="kokoro",
        voices=[{"voice_id": "af_bella", "name": "Bella"}, {"voice_id": "af_sky", "name": "Sky"}],
    )
    assert captured["payload"]["voice"] == "af_bella"
    assert captured["payload"]["model"] == "kokoro"
