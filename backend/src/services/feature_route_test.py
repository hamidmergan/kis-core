"""Test whether a configured feature route actually works end-to-end.

The admin tab's "test" button on each feature row calls this. Distinct from
``provider_probe`` (which only checks raw reachability of an endpoint): this
routes a minimal real request through the feature-specific endpoint with the
admin-chosen model, so an admin can tell apart "provider is online" from
"this model is actually wired up for this feature".

Returns a ``FeatureTestResult`` with status="ok"/"error" and an error string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger

from src.services.protocols import make_adapter
from src.services.protocols.deepl import DeepLAdapter
from src.services.protocols.docling import DoclingAdapter
from src.services.protocols.openai_compat import OpenAICompatAdapter


_TIMEOUT = 15.0


@dataclass
class FeatureTestResult:
    status: str  # "ok" | "error"
    error: Optional[str] = None


# Features whose openai_compat path runs via /v1/chat/completions.
_CHAT_LIKE_FEATURES = frozenset({"chat", "vision", "ocr", "doc_translate", "screencast_translate"})


def test_feature_route(
    *,
    feature: str,
    protocol: str,
    base_url: str,
    api_key: Optional[str],
    model_name: Optional[str],
    voices: Optional[list] = None,
) -> FeatureTestResult:
    """Dispatch a feature-appropriate test request and report ok/error."""
    try:
        if protocol == OpenAICompatAdapter.PROTOCOL:
            return _test_openai_compat(
                feature=feature,
                base_url=base_url,
                api_key=api_key,
                model_name=model_name,
                voices=voices or [],
            )
        # Non-openai protocols are single-capability: probe IS the feature test.
        adapter = make_adapter(protocol=protocol, base_url=base_url, api_key=api_key)
        if isinstance(adapter, (DeepLAdapter, DoclingAdapter)):
            result = adapter.probe()
            return FeatureTestResult(status=result.status, error=result.error)
        return FeatureTestResult(status="error", error=f"unsupported protocol: {protocol}")
    except Exception as e:  # noqa: BLE001 - test must never crash the caller
        logger.exception("feature test crashed for protocol={} feature={}", protocol, feature)
        return FeatureTestResult(status="error", error=f"{type(e).__name__}: {e}")


# ─── OpenAI-compat per-feature tests ────────────────────────────────────────


def _openai_headers(api_key: Optional[str]) -> dict:
    h = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _build_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1") and path.startswith("/v1/"):
        return base + path[len("/v1"):]
    return base + path


def _test_openai_compat(
    *,
    feature: str,
    base_url: str,
    api_key: Optional[str],
    model_name: Optional[str],
    voices: list,
) -> FeatureTestResult:
    if feature == "tts":
        if not model_name:
            return FeatureTestResult(status="error", error="model_name_not_set")
        if not voices:
            return FeatureTestResult(status="error", error="no_voices_configured")
        return _post_tts(base_url, api_key, model_name, voices)
    if feature in ("stt", "image_gen", "image_edit"):
        # Cheap real tests for these would need multipart audio / image fixtures
        # and would actually generate output (costs time + quota). Instead, fall
        # back to verifying the provider answers at all — same signal as the
        # provider's reachability probe. /v1/models is not a model-existence
        # check here; many providers omit image / audio models from that list.
        return _check_reachable(base_url, api_key)
    if not model_name:
        return FeatureTestResult(status="error", error="model_name_not_set")
    if feature in _CHAT_LIKE_FEATURES:
        return _post_chat_completion(base_url, api_key, model_name)
    if feature == "embedding":
        return _post_embedding(base_url, api_key, model_name)
    return FeatureTestResult(status="error", error=f"unknown feature: {feature}")


def _post_chat_completion(
    base_url: str, api_key: Optional[str], model_name: str
) -> FeatureTestResult:
    url = _build_url(base_url, "/v1/chat/completions")
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    return _post_json(url, api_key, payload)


def _post_embedding(
    base_url: str, api_key: Optional[str], model_name: str
) -> FeatureTestResult:
    url = _build_url(base_url, "/v1/embeddings")
    payload = {"model": model_name, "input": "ping"}
    return _post_json(url, api_key, payload)


def _post_tts(
    base_url: str, api_key: Optional[str], model_name: str, voices: list
) -> FeatureTestResult:
    url = _build_url(base_url, "/v1/audio/speech")
    voice_id = voices[0]["voice_id"]
    payload = {"model": model_name, "input": "ping", "voice": voice_id}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=_openai_headers(api_key), json=payload)
    except httpx.HTTPError:
        return FeatureTestResult(status="error", error="unreachable")
    result = _classify_http(resp, expect_json=False)
    if result.status == "error" and resp.status_code == 404:
        return FeatureTestResult(status="error", error="tts_speech_endpoint_not_found")
    return result


def _check_reachable(base_url: str, api_key: Optional[str]) -> FeatureTestResult:
    """Reachability-only test for features we don't exercise end-to-end.

    Sends a single ``GET /v1/models`` and treats any non-5xx response as alive
    (auth-protected 401, no-such-model 404 inside the body, etc. all still
    prove the server is answering). Network failures and 5xx surface as
    errors. We deliberately do NOT inspect the response body — we just want
    to know "is there something at the other end of the wire?".
    """
    url = _build_url(base_url, "/v1/models")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url, headers=headers)
    except httpx.HTTPError:
        return FeatureTestResult(status="error", error="unreachable")
    if resp.status_code >= 500:
        return FeatureTestResult(status="error", error="server_error")
    if resp.status_code in (401, 403):
        return FeatureTestResult(status="error", error="auth_rejected")
    return FeatureTestResult(status="ok")


def _post_json(url: str, api_key: Optional[str], payload: dict) -> FeatureTestResult:
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=_openai_headers(api_key), json=payload)
    except httpx.HTTPError:
        return FeatureTestResult(status="error", error="unreachable")
    return _classify_http(resp, expect_json=True)


def _classify_http(resp: httpx.Response, *, expect_json: bool) -> FeatureTestResult:
    status = resp.status_code
    if 200 <= status < 300:
        return FeatureTestResult(status="ok")
    if status in (401, 403):
        return FeatureTestResult(status="error", error="auth_rejected")
    if status == 404:
        return FeatureTestResult(status="error", error="endpoint_not_found")
    if status >= 500:
        return FeatureTestResult(status="error", error="server_error")
    # For error responses (non-2xx) always try to extract a human-readable
    # message from the body — even for TTS (expect_json=False) since error
    # bodies are JSON even when the success response would be binary audio.
    detail = ""
    try:
        body = resp.json()
        # OpenAI format: {"error": {"message": "..."}}
        err = body.get("error", {})
        if isinstance(err, dict):
            detail = err.get("message", "")
        # Some servers: {"detail": {"message": "..."}} or {"detail": "..."}
        if not detail:
            d = body.get("detail", "")
            if isinstance(d, dict):
                detail = d.get("message", "")
            elif isinstance(d, str):
                detail = d
        if not detail:
            detail = body.get("message", "")
    except Exception:
        pass
    if not detail:
        detail = resp.text[:200] if resp.text else ""
    if detail:
        return FeatureTestResult(status="error", error=detail)
    return FeatureTestResult(status="error", error=f"http_{status}")
