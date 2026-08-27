"""Unit tests for feature_route_check — TTS path changes and STT model validation."""
import pytest
from unittest.mock import patch, MagicMock
from src.services.feature_route_check import FeatureTestResult


def test_tts_test_omits_model_when_not_set(monkeypatch):
    """Without a model name the call still has to go out, the field is dropped."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    captured = {}

    def fake_post(self, url, **kwargs):
        captured["payload"] = kwargs.get("json", {})
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="tts",
        protocol="openai_compat",
        base_url="http://tts.example.com",
        api_key=None,
        model_name=None,
        voices=[{"voice_id": "af_bella", "name": "Bella"}],
    )
    assert result.status == "ok"
    assert "model" not in captured["payload"]
    assert captured["payload"]["voice"] == "af_bella"


def test_tts_test_returns_error_when_no_voices():
    """run_feature_route_test for TTS with empty voices must return no_voices_configured."""
    from src.services.feature_route_check import run_feature_route_test

    result = run_feature_route_test(
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
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    captured = {}

    def fake_post(self, url, **kwargs):
        captured["payload"] = kwargs.get("json", {})
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    run_feature_route_test(
        feature="tts",
        protocol="openai_compat",
        base_url="http://tts.example.com",
        api_key=None,
        model_name="kokoro",
        voices=[{"voice_id": "af_bella", "name": "Bella"}, {"voice_id": "af_sky", "name": "Sky"}],
    )
    assert captured["payload"]["voice"] == "af_bella"
    assert captured["payload"]["model"] == "kokoro"


def test_stt_test_posts_real_transcription_when_model_set(monkeypatch):
    """A valid model answers, the bait is rejected."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    calls: list = []

    def fake_post(self, url, **kwargs):
        model = (kwargs.get("data") or {}).get("model")
        calls.append({"url": url, "model": model, "files": kwargs.get("files")})
        resp = MagicMock(spec=httpx.Response)
        # Canary (clearly-invalid name) gets rejected; the user's real model passes.
        if "canary" in (model or ""):
            resp.status_code = 404
            resp.json.return_value = {"detail": "model not found"}
            resp.text = '{"detail":"model not found"}'
        else:
            resp.status_code = 200
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="stt",
        protocol="openai_compat",
        base_url="http://stt.example.com",
        api_key="secret",
        model_name="whisper-large-v3",
    )
    assert result.status == "ok"
    user_call = next(c for c in calls if c["model"] == "whisper-large-v3")
    assert user_call["url"].endswith("/v1/audio/transcriptions")
    assert user_call["files"]["file"][0] == "probe.wav"
    assert user_call["files"]["file"][1].startswith(b"RIFF")


def test_stt_canary_passes_no_backend_evidence_returns_soft_warning(monkeypatch):
    """If the bait gets through too, it stays at the cautious hint."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    def fake_post(self, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.headers = {}  # bare response, no proof of real backend
        resp.json.return_value = ""
        resp.text = '""'
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="stt",
        protocol="openai_compat",
        base_url="http://llm.example.com",
        api_key="k",
        model_name="anything-the-admin-typed",
    )
    assert result.status == "ok"
    assert result.warning == "stt_model_not_validated_by_provider"
    assert result.error is None


def test_stt_canary_passes_with_backend_evidence_upgrades_warning(monkeypatch):
    """Gateway headers prove a real service behind it."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    def fake_post(self, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        # Mirrors actual response headers we captured during debugging.
        resp.headers = {
            "x-ratelimit-remaining-minute": "8",
            "x-kong-upstream-latency": "247",
            "via": "kong/3.6.1",
            "x-kong-request-id": "abc123",
        }
        resp.json.return_value = ""
        resp.text = '""'
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="stt",
        protocol="openai_compat",
        base_url="https://llm.example.com/v1",
        api_key="k",
        model_name="whisper-large-v2",
    )
    assert result.status == "ok"
    assert result.warning == "stt_endpoint_verified_model_unvalidated"
    assert result.error is None


def test_stt_test_reports_error_for_unknown_model(monkeypatch):
    """A rejected model name has to become visible."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    def fake_post(self, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 400
        resp.json.return_value = {"error": {"message": "model 'nope' not found"}}
        resp.text = '{"error":{"message":"model \'nope\' not found"}}'
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="stt",
        protocol="openai_compat",
        base_url="http://stt.example.com",
        api_key=None,
        model_name="nope",
    )
    assert result.status == "error"
    assert "nope" in (result.error or "")


def test_stt_test_requires_model_name():
    """A route without a model is not usable."""
    from src.services.feature_route_check import run_feature_route_test

    result = run_feature_route_test(
        feature="stt",
        protocol="openai_compat",
        base_url="http://stt.example.com",
        api_key=None,
        model_name=None,
    )
    assert result.status == "error"
    assert result.error == "model_name_not_set"


def test_image_gen_requires_model_name():
    """A configured image_gen route without a model is not usable."""
    from src.services.feature_route_check import run_feature_route_test

    result = run_feature_route_test(
        feature="image_gen",
        protocol="openai_compat",
        base_url="http://img.example.com",
        api_key=None,
        model_name=None,
    )
    assert result.status == "error"
    assert result.error == "model_name_not_set"


def test_image_edit_requires_model_name():
    from src.services.feature_route_check import run_feature_route_test

    result = run_feature_route_test(
        feature="image_edit",
        protocol="openai_compat",
        base_url="http://img.example.com",
        api_key=None,
        model_name=None,
    )
    assert result.status == "error"
    assert result.error == "model_name_not_set"


def test_image_gen_posts_real_generation(monkeypatch):
    """The image call has to go to the image endpoint, not to the model list."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    captured = {}

    def fake_post(self, url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs.get("json")
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="image_gen",
        protocol="openai_compat",
        base_url="http://img.example.com",
        api_key="k",
        model_name="flux.1-dev",
    )
    assert result.status == "ok"
    assert captured["url"].endswith("/v1/images/generations")
    assert captured["payload"]["model"] == "flux.1-dev"


def test_image_gen_rejects_invalid_model(monkeypatch):
    """An unknown image model has to show the provider's error."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    def fake_post(self, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 404
        resp.json.side_effect = ValueError("not json")
        resp.text = "Model Not Found"
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="image_gen",
        protocol="openai_compat",
        base_url="http://img.example.com",
        api_key="k",
        model_name="bogus",
    )
    assert result.status == "error"
    assert "Model Not Found" in (result.error or "")


def test_image_edit_posts_standard_openai_form(monkeypatch):
    """Image editing uses the same usual transfer as the others."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    captured = {}

    def fake_post(self, url, **kwargs):
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        captured["files"] = kwargs.get("files")
        captured["headers"] = kwargs.get("headers") or {}
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="image_edit",
        protocol="openai_compat",
        base_url="http://img.example.com",
        api_key="k",
        model_name="flux.1-kontext",
    )
    assert result.status == "ok"
    assert captured["url"].endswith("/v1/images/edits")
    assert not captured["url"].endswith("/edits/")
    # The probe needs the same numbers as operation.
    assert captured["data"]["model"] == "flux.1-kontext"
    assert captured["data"]["prompt"] == "test"
    assert captured["data"]["n"] == "1"
    assert captured["data"]["size"] == "1024x1024"
    assert captured["data"]["guidance_scale"] == "3.5"
    assert captured["data"]["num_inference_steps"] == "25"
    assert "inference-service" not in captured["headers"]
    assert captured["files"]["image"][1].startswith(b"\x89PNG")


def test_image_gen_does_not_use_models_listing(monkeypatch):
    """A pure chat list must not wave image generation through."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    get_called = {"n": 0}

    def fake_get(self, url, **kwargs):
        # If the implementation reaches for the model list, the test fails loudly.
        get_called["n"] += 1
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.return_value = {"data": [{"id": "gemma-3-27b-it"}]}
        return resp

    def fake_post(self, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 404
        resp.json.side_effect = ValueError("not json")
        resp.text = "Model Not Found"
        return resp

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="image_gen",
        protocol="openai_compat",
        base_url="http://img.example.com",
        api_key=None,
        model_name="gemma-3-27b-it",
    )
    assert get_called["n"] == 0, "image_gen must not consult /v1/models"
    assert result.status == "error"
    assert "Model Not Found" in (result.error or "")


def test_classify_http_passes_plain_text_404(monkeypatch):
    """A plain text error from the provider must not be swallowed."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    def fake_post(self, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 404
        resp.json.side_effect = ValueError("not json")
        resp.text = "Model Not Found"
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="stt",
        protocol="openai_compat",
        base_url="http://stt.example.com",
        api_key=None,
        model_name="some",
    )
    assert result.status == "error"
    assert result.error == "Model Not Found"


def test_stt_test_404_with_model_detail_surfaces_body(monkeypatch):
    """The reason from the body has to come through, not a blanket error."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    def fake_post(self, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 404
        resp.json.return_value = {"detail": "Model fake not found"}
        resp.text = '{"detail":"Model fake not found"}'
        return resp

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = run_feature_route_test(
        feature="stt",
        protocol="openai_compat",
        base_url="http://stt.example.com",
        api_key=None,
        model_name="fake",
    )
    assert result.status == "error"
    assert "Model fake not found" in (result.error or "")
