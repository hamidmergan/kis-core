"""Unit tests for feature_route_check — TTS path changes and STT model validation."""
import pytest
from unittest.mock import patch, MagicMock
from src.services.feature_route_check import FeatureTestResult


def test_tts_test_omits_model_when_not_set(monkeypatch):
    """TTS with model_name=None must still POST — the model field is omitted.

    Kokoro and other single-model TTS servers reject requests that carry a
    ``model`` field, so an empty model_name must not block the request.
    """
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
    """STT with model_name must POST to /v1/audio/transcriptions. A valid
    model returns 200 for the user's name and 4xx for the canary probe —
    the test then reports 'ok'."""
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
    """If the canary passes AND the response carries no rate-limit or
    gateway headers, we can't prove the request hit a real backend — use
    the cautious warning code."""
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
        base_url="http://kisski.example.com",
        api_key="k",
        model_name="anything-the-admin-typed",
    )
    assert result.status == "ok"
    assert result.warning == "stt_model_not_validated_by_provider"
    assert result.error is None


def test_stt_canary_passes_with_backend_evidence_upgrades_warning(monkeypatch):
    """KISSKI returns 200 with Kong + rate-limit headers proving the request
    was forwarded to the real Whisper backend (not a stub). The warning is
    upgraded to the positive 'endpoint verified' variant."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    def fake_post(self, url, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        # Mirrors actual KISSKI response headers we captured during debugging.
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
        base_url="https://saia.gwdg.de/v1",
        api_key="k",
        model_name="whisper-large-v2",
    )
    assert result.status == "ok"
    assert result.warning == "stt_endpoint_verified_model_unvalidated"
    assert result.error is None


def test_stt_test_reports_error_for_unknown_model(monkeypatch):
    """When the upstream rejects the model name with 400, the test must
    surface that — not show 'reachable'."""
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
    """A configured STT route without a model is not usable — must return
    'model_name_not_set' instead of silently reporting 'reachable'."""
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
    """image_gen must POST to /v1/images/generations so providers (KISSKI)
    whose /v1/models listing is undifferentiated can't pass a chat model id
    off as an image model."""
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
    """An unknown image model must surface the provider's error, not a
    silent 'ok' from a stale /v1/models fast path."""
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
    """image_edit uses the same transport as image_gen / chat / vision:
    standard OpenAI-style — model in body, no trailing slash, no provider-
    specific headers. Providers that need something else (KISSKI's
    inference-service header) are explicitly NOT supported via this path."""
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
    # Probe payload must include the numeric defaults the production task
    # also sends — without them myLab crashes server-side with a TypeError.
    assert captured["data"]["model"] == "flux.1-kontext"
    assert captured["data"]["prompt"] == "test"
    assert captured["data"]["n"] == "1"
    assert captured["data"]["size"] == "1024x1024"
    assert captured["data"]["guidance_scale"] == "3.5"
    assert captured["data"]["num_inference_steps"] == "25"
    assert "inference-service" not in captured["headers"]
    assert captured["files"]["image"][1].startswith(b"\x89PNG")


def test_image_gen_does_not_use_models_listing(monkeypatch):
    """Regression: a chat-only listing must NOT make image_gen pass. Earlier
    code fast-pathed on any /v1/models match — that hid chat-model misconfigs
    as 'reachable' (the original bug we removed)."""
    from src.services.feature_route_check import run_feature_route_test
    import httpx

    get_called = {"n": 0}

    def fake_get(self, url, **kwargs):
        # If the implementation hits /v1/models at all for image_gen, we
        # surface that here so the test fails loudly.
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
    """KISSKI returns 404 with plain text body 'Model Not Found' — must not
    be swallowed as generic 'endpoint_not_found'."""
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
    """vLLM/myLab returns 404 with {"detail":"Model X not found"} for an
    unknown model. The body detail must surface — not a generic
    'endpoint_not_found' which would falsely blame the endpoint."""
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
