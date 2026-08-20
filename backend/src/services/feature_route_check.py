"""Test whether a configured feature route actually works end-to-end.

The admin tab's "test" button on each feature row calls this. Distinct from
``provider_probe`` (which only checks raw reachability of an endpoint): this
routes a minimal real request through the feature-specific endpoint with the
admin-chosen model, so an admin can tell apart "provider is online" from
"this model is actually wired up for this feature".

Returns a ``FeatureTestResult`` with status="ok"/"error" and an error string.
"""

from __future__ import annotations

import struct
import zlib
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
    # Soft signal alongside status="ok" — the request succeeded but a caveat
    # applies (e.g. some STT silently accepts any model name, so we can't
    # actually verify the model is valid).
    warning: Optional[str] = None


# Features whose openai_compat path runs via /v1/chat/completions.
_CHAT_LIKE_FEATURES = frozenset({"chat", "vision", "ocr", "doc_translate", "transcript_translate"})


def run_feature_route_test(
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
        # model_name is optional for TTS — some providers (e.g. Kokoro) only
        # serve one model and reject requests that carry a ``model`` field.
        # Others (e.g. myLab/vLLM) need it. We pass through whatever was
        # configured; _post_tts will omit the field when empty.
        if not voices:
            return FeatureTestResult(status="error", error="no_voices_configured")
        return _post_tts(base_url, api_key, model_name, voices)
    if feature == "stt":
        # Exercise the real endpoint with a tiny silence WAV so an invalid
        # model name is actually rejected. Like chat/embedding, the model is
        # required — a configured STT route with no model is not usable.
        if not model_name:
            return FeatureTestResult(status="error", error="model_name_not_set")
        return _post_stt(base_url, api_key, model_name)
    if feature in ("image_gen", "image_edit"):
        if not model_name:
            return FeatureTestResult(status="error", error="model_name_not_set")
        return _check_image_model(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            edit=feature == "image_edit",
        )
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
    base_url: str, api_key: Optional[str], model_name: Optional[str], voices: list
) -> FeatureTestResult:
    url = _build_url(base_url, "/v1/audio/speech")
    voice_id = voices[0]["voice_id"]
    payload: dict = {"input": "ping", "voice": voice_id}
    if model_name:
        payload["model"] = model_name
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=_openai_headers(api_key), json=payload)
    except httpx.HTTPError:
        return FeatureTestResult(status="error", error="unreachable")
    result = _classify_http(resp, expect_json=False)
    if result.status == "error" and resp.status_code == 404:
        return FeatureTestResult(status="error", error="tts_speech_endpoint_not_found")
    return result


def _silence_wav(duration_sec: float = 0.1, sample_rate: int = 16000) -> bytes:
    """Build a minimal mono 16-bit PCM WAV of silence for STT model probing."""
    num_samples = int(duration_sec * sample_rate)
    data_size = num_samples * 2
    byte_rate = sample_rate * 2
    return b"".join([
        b"RIFF",
        struct.pack("<I", 36 + data_size),
        b"WAVE",
        b"fmt ",
        struct.pack("<I", 16),
        struct.pack("<H", 1),
        struct.pack("<H", 1),
        struct.pack("<I", sample_rate),
        struct.pack("<I", byte_rate),
        struct.pack("<H", 2),
        struct.pack("<H", 16),
        b"data",
        struct.pack("<I", data_size),
        b"\x00" * data_size,
    ])


# An obviously-bogus model name we use to detect providers whose
# /v1/audio/transcriptions silently ignores the ``model`` field — i.e. accept
# anything, return 200 with an empty body. Without this canary, a passing
# real probe would falsely report 'ok' for any string the admin typed.
_STT_CANARY_MODEL = "__kis_canary_invalid_model_xyz__"


def _stt_probe(
    base_url: str, api_key: Optional[str], model_name: str
) -> httpx.Response:
    url = _build_url(base_url, "/v1/audio/transcriptions")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    files = {"file": ("probe.wav", _silence_wav(), "audio/wav")}
    data = {"model": model_name, "response_format": "text"}
    with httpx.Client(timeout=_TIMEOUT) as client:
        return client.post(url, headers=headers, files=files, data=data)


def _has_real_backend_evidence(resp: httpx.Response) -> int:
    """Count signals in the response headers that prove the request reached
    a real backend (not a stub that always returns 200).

    Two independent signals = high confidence:
    - ``x-ratelimit-*`` / ``ratelimit-*`` headers prove the gateway is
      counting our request against a quota.
    - ``x-kong-upstream-latency`` proves Kong forwarded to an upstream that
      took measurable time to respond.
    - ``via`` (Kong / Cloudflare / etc.) proves a real gateway routed it.
    - ``x-request-id`` / ``x-kong-request-id`` proves per-request tracking.
    """
    headers = {k.lower(): v for k, v in resp.headers.items()}
    n = 0
    if any(k.startswith("x-ratelimit-") or k.startswith("ratelimit-") for k in headers):
        n += 1
    if "x-kong-upstream-latency" in headers:
        n += 1
    if "via" in headers:
        n += 1
    if any(k in headers for k in ("x-request-id", "x-kong-request-id")):
        n += 1
    return n


def _post_stt(
    base_url: str, api_key: Optional[str], model_name: str
) -> FeatureTestResult:
    try:
        resp = _stt_probe(base_url, api_key, model_name)
    except httpx.HTTPError:
        return FeatureTestResult(status="error", error="unreachable")
    primary = _classify_http(resp, expect_json=False)
    if primary.status != "ok":
        return primary
    # The user's model came back ok — but some providers
    # accept any model name and silently fall back to a default. Send a
    # canary with a guaranteed-invalid name: if THAT also passes, the model
    # field is being ignored and we can't validate the name. We still surface
    # 'ok' (the endpoint works) and use the response headers to upgrade the
    # warning when we have strong evidence the request hit a real backend.
    try:
        canary = _stt_probe(base_url, api_key, _STT_CANARY_MODEL)
    except httpx.HTTPError:
        return primary
    if 200 <= canary.status_code < 300:
        evidence = _has_real_backend_evidence(resp)
        warning_key = (
            "stt_endpoint_verified_model_unvalidated"
            if evidence >= 2
            else "stt_model_not_validated_by_provider"
        )
        return FeatureTestResult(status="ok", warning=warning_key)
    return primary


def _make_grey_png(side: int = 64) -> bytes:
    """Build a side×side mono PNG of mid-grey.

    A 1×1 PNG was rejected by an image-edit reader ("broken data stream" — a
    PIL/cv2 stack that can't handle degenerate sizes). 64×64 stays under
    ~200 bytes thanks to PNG's deflate but is large enough that any sane
    image reader will accept it.
    """
    raw = b"".join(b"\x00" + b"\x80" * side for _ in range(side))
    z = zlib.compress(raw)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + tag
            + body
            + struct.pack(">I", zlib.crc32(tag + body))
        )

    ihdr = struct.pack(">IIBBBBB", side, side, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", z)
        + chunk(b"IEND", b"")
    )


_TINY_PNG = _make_grey_png(64)

# Image generation can legitimately take 10–30 s; bumped from the default
# 15 s so a slow-but-valid model isn't misreported as 'unreachable'.
_IMAGE_TIMEOUT = 60.0


def _check_image_model(
    *, base_url: str, api_key: Optional[str], model_name: str, edit: bool
) -> FeatureTestResult:
    """Validate an image model with a real POST — same pattern as chat/vision.

    Image gen and image edit each go through the same code path the
    production job uses (``general_tasks.run_image_*``) so a passing test
    proves the live feature will also work — no transport-style divergence
    between probe and prod.
    """
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with httpx.Client(timeout=_IMAGE_TIMEOUT, headers=headers) as client:
            if edit:
                # Mirror the production task's payload (general_tasks.run_image_edit)
                # — myLab returns a Python TypeError if guidance_scale / steps
                # / n / size aren't supplied explicitly. A probe with fewer
                # fields would falsely report "broken endpoint" when in fact
                # the live job would work fine.
                url = _build_url(base_url, "/v1/images/edits")
                resp = client.post(
                    url,
                    files={"image": ("probe.png", _TINY_PNG, "image/png")},
                    data={
                        "model": model_name,
                        "prompt": "test",
                        "response_format": "b64_json",
                        "n": "1",
                        "size": "1024x1024",
                        "quality": "standard",
                        "guidance_scale": "3.5",
                        "num_inference_steps": "25",
                    },
                )
            else:
                url = _build_url(base_url, "/v1/images/generations")
                payload = {
                    "model": model_name,
                    "prompt": "test",
                    "size": "256x256",
                    "n": 1,
                    "response_format": "b64_json",
                }
                resp = client.post(
                    url, headers={"Content-Type": "application/json"}, json=payload
                )
    except httpx.HTTPError:
        return FeatureTestResult(status="error", error="unreachable")
    return _classify_http(resp, expect_json=True)


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
    # For non-2xx (including 5xx), try to extract a human-readable detail
    # from the body first — many servers (incl. vLLM/myLab) return 404 with
    # {"detail":"Model X not found"}, others return plain "Model Not Found",
    # and myLab's broken image-edit returns plain "Internal Server Error".
    # All of these tell the admin far more than a generic 'server_error'.
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
    # Plain-text body fallback (e.g. a plain "Model Not Found").
    if not detail and resp.text:
        detail = resp.text.strip()[:200]
    if detail:
        return FeatureTestResult(status="error", error=detail)
    if status >= 500:
        return FeatureTestResult(status="error", error="server_error")
    if status == 404:
        return FeatureTestResult(status="error", error="endpoint_not_found")
    return FeatureTestResult(status="error", error=f"http_{status}")
