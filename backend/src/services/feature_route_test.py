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
from src.services.protocols.kokoro import KokoroAdapter
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
) -> FeatureTestResult:
    """Dispatch a feature-appropriate test request and report ok/error."""
    try:
        if protocol == OpenAICompatAdapter.PROTOCOL:
            return _test_openai_compat(
                feature=feature,
                base_url=base_url,
                api_key=api_key,
                model_name=model_name,
            )
        # Non-openai protocols are single-capability: probe IS the feature test.
        adapter = make_adapter(protocol=protocol, base_url=base_url, api_key=api_key)
        if isinstance(adapter, (DeepLAdapter, DoclingAdapter, KokoroAdapter)):
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
) -> FeatureTestResult:
    if not model_name:
        return FeatureTestResult(status="error", error="model name not set")

    if feature in _CHAT_LIKE_FEATURES:
        return _post_chat_completion(base_url, api_key, model_name)
    if feature == "embedding":
        return _post_embedding(base_url, api_key, model_name)
    if feature == "tts":
        return _post_tts(base_url, api_key, model_name)
    if feature in ("stt", "image_gen", "image_edit"):
        # Cheap real tests for these would need multipart audio / image fixtures
        # and would actually generate output (costs time + quota). Instead, fall
        # back to verifying the provider answers at all — same signal as the
        # provider's reachability probe. /v1/models is not a model-existence
        # check here; many providers omit image / audio models from that list.
        return _check_reachable(base_url, api_key)
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
    base_url: str, api_key: Optional[str], model_name: str
) -> FeatureTestResult:
    url = _build_url(base_url, "/v1/audio/speech")
    payload = {"model": model_name, "input": "ping", "voice": "alloy"}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=_openai_headers(api_key), json=payload)
    except httpx.HTTPError as e:
        return FeatureTestResult(status="error", error=f"unreachable: {type(e).__name__}: {e}")
    return _classify_http(resp, expect_json=False)


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
    except httpx.HTTPError as e:
        return FeatureTestResult(status="error", error=f"unreachable: {type(e).__name__}: {e}")
    if resp.status_code >= 500:
        return FeatureTestResult(status="error", error=f"server error (HTTP {resp.status_code})")
    if resp.status_code in (401, 403):
        return FeatureTestResult(status="error", error=f"auth rejected (HTTP {resp.status_code})")
    return FeatureTestResult(status="ok")


def _post_json(url: str, api_key: Optional[str], payload: dict) -> FeatureTestResult:
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=_openai_headers(api_key), json=payload)
    except httpx.HTTPError as e:
        return FeatureTestResult(status="error", error=f"unreachable: {type(e).__name__}: {e}")
    return _classify_http(resp, expect_json=True)


def _classify_http(resp: httpx.Response, *, expect_json: bool) -> FeatureTestResult:
    status = resp.status_code
    if 200 <= status < 300:
        return FeatureTestResult(status="ok")
    if status in (401, 403):
        return FeatureTestResult(status="error", error=f"auth rejected (HTTP {status})")
    if status == 404:
        return FeatureTestResult(status="error", error="endpoint not found (HTTP 404)")
    # Surface server-side reason if available; many openai-compat servers
    # return a structured error body for unknown models / bad input.
    detail = ""
    try:
        if expect_json:
            body = resp.json()
            detail = body.get("error", {}).get("message") or body.get("detail") or ""
    except Exception:
        pass
    if not detail:
        detail = resp.text[:200] if resp.text else ""
    return FeatureTestResult(status="error", error=f"HTTP {status}: {detail}".strip(": "))
