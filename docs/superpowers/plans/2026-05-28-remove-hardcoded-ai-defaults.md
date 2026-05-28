# Remove Hardcoded AI Defaults — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all hardcoded AI model/voice fallbacks (`tts-1`, `whisper-large-v2`, `alloy`) so that missing admin KI configuration surfaces a clear error instead of silently using a wrong default.

**Architecture:** Extend the existing `FeatureNotConfigured` / `ValueError` fail-fast pattern already used for `image_gen`, `vision`, `image_edit` to cover STT model, TTS model, and TTS voice. Each removal is isolated to the file that owns the constant.

**Tech Stack:** Python 3.11 (run tests via `docker exec kis-backend`), pytest, Next.js i18n (next-intl), TypeScript.

---

## File Map

| File | Change |
|---|---|
| `backend/src/services/openai_compat_tts.py` | Remove `_DEFAULT_VOICE`, `_DEFAULT_MODEL`; make `model` required; raise `ValueError` on empty `voice_id` |
| `backend/src/services/feature_router.py` | `make_tts_client`: raise `FeatureNotConfigured` if `binding.model` is falsy |
| `backend/src/dependencies.py` | Remove `"whisper-large-v2"` and `"tts-1"` fallbacks; raise `FeatureNotConfigured` |
| `backend/src/services/openai_compat_llm/base.py` | Make `whisper_model` a required parameter |
| `backend/src/services/feature_route_test.py` | Remove `_DEFAULT_TTS_MODEL`; add `voices` param to `_test_openai_compat` and `_post_tts`; new error `no_voices_configured` |
| `backend/src/routes/admin/providers.py` | Pass `provider.get("voices", [])` to `test_feature_route()` |
| `frontend/messages/en.json` | Add `no_voices_configured` under `testErrors` |
| `frontend/messages/de.json` | Add `no_voices_configured` under `testErrors` |
| `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx` | Add `"no_voices_configured"` to `knownCodes` set |
| `backend/tests/test_openai_compat_tts.py` | New test file |
| `backend/tests/test_feature_route_test.py` | New test file |

---

## Task 1: Remove hardcoded defaults from `openai_compat_tts.py`

**Files:**
- Modify: `backend/src/services/openai_compat_tts.py:14-15,50,96-105`
- Create: `backend/tests/test_openai_compat_tts.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_openai_compat_tts.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
docker exec kis-backend python -m pytest tests/test_openai_compat_tts.py -v
```

Expected: 3 FAILED (currently the code silently uses `_DEFAULT_VOICE` / `_DEFAULT_MODEL`).

- [ ] **Step 3: Implement the changes**

Edit `backend/src/services/openai_compat_tts.py`. The full updated top section and `__init__` + `_synthesize_one`:

```python
"""OpenAI-compatible TTS client.

Endpoints used (OpenAI Audio spec):
    POST /v1/audio/speech   -> audio bytes (mp3)
    GET  /v1/models         -> health probe

Works with any OpenAI-compatible TTS server (openedai-speech, XTTS-v2, etc.).
Voices are managed in the providers.voices DB column, not hardcoded here.
"""
from __future__ import annotations

import httpx

_CHUNK_MAX = 10_000
_CHUNK_MIN = 9_500
```

(Remove lines 14–15: `_DEFAULT_VOICE = "alloy"` and `_DEFAULT_MODEL = "tts-1"`)

Update `__init__` — remove the default value for `model`:

```python
    def __init__(self, base_url: str, model: str, api_key: str = "not-needed"):
```

Update `_synthesize_one` — replace the silent fallback with a `ValueError`:

```python
    def _synthesize_one(
        self,
        client: httpx.Client,
        text: str,
        *,
        voice_id: str = "default",
        speed: float = 1.0,
    ) -> bytes:
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if not voice_id or voice_id == "default":
            raise ValueError(
                "voice_id must be set — configure voices for this provider in the admin KI panel"
            )
        voice = voice_id
        payload: dict = {
            "model": self._model,
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "mp3",
        }
        response = client.post(
            f"{self._base_url}/v1/audio/speech",
            json=payload,
            headers=self._headers(),
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"TTS API error ({response.status_code}): {response.text[:300]}"
            )
        return response.content
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker exec kis-backend python -m pytest tests/test_openai_compat_tts.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/openai_compat_tts.py backend/tests/test_openai_compat_tts.py
git commit -m "feat: remove hardcoded TTS defaults from openai_compat_tts — raise on missing voice_id/model"
```

---

## Task 2: Fix `feature_router.py:make_tts_client`

**Files:**
- Modify: `backend/src/services/feature_router.py:125-133`

After Task 1, calling `OpenAICompatTTSClient(base_url=...)` without `model=` raises a bare `TypeError`. Catch this at the source by raising `FeatureNotConfigured` with a useful message.

- [ ] **Step 1: Add test for missing model in `make_tts_client`**

Add to `backend/tests/test_openai_compat_tts.py`:

```python
def test_make_tts_client_raises_when_no_model():
    """make_tts_client must raise FeatureNotConfigured when binding has no model."""
    from src.services.feature_router import make_tts_client, FeatureBinding, FeatureNotConfigured
    binding = FeatureBinding(
        feature="tts",
        provider={"base_url": "http://tts.example.com", "name": "KokoroTTS"},
        model=None,
    )
    with pytest.raises(FeatureNotConfigured, match="model_name"):
        make_tts_client(binding)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
docker exec kis-backend python -m pytest tests/test_openai_compat_tts.py::test_make_tts_client_raises_when_no_model -v
```

Expected: FAILED (currently raises `TypeError`, not `FeatureNotConfigured`).

- [ ] **Step 3: Implement fix in `feature_router.py`**

Replace the `make_tts_client` function (lines 125–133) with:

```python
def make_tts_client(binding: FeatureBinding):
    """Return an OpenAICompatTTSClient for the chosen TTS provider."""
    from src.services.openai_compat_tts import OpenAICompatTTSClient

    if not binding.model:
        raise FeatureNotConfigured(
            f"tts provider '{binding.provider.get('name', '')}' has no model_name — "
            "set it in the admin KI panel"
        )
    provider = binding.provider
    return OpenAICompatTTSClient(
        base_url=provider["base_url"],
        model=binding.model,
        api_key=provider.get("api_key") or "not-needed",
    )
```

Note: The original code omitted `api_key` from the kwargs dict. This is a bug fix as well — the API key was always being passed as "not-needed". The runtime path via `get_tts_client_for_provider` in `dependencies.py` sets it correctly; `make_tts_client` via `feature_router` did not.

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker exec kis-backend python -m pytest tests/test_openai_compat_tts.py -v
```

Expected: all 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/feature_router.py backend/tests/test_openai_compat_tts.py
git commit -m "feat: make_tts_client raises FeatureNotConfigured when model_name is not set"
```

---

## Task 3: Fix `dependencies.py` — remove STT and TTS fallbacks

**Files:**
- Modify: `backend/src/dependencies.py:142,194`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_dependencies_tts_stt.py`:

```python
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
    monkeypatch.setattr("src.dependencies.feature_router.resolve", lambda f: binding)

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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
docker exec kis-backend python -m pytest tests/test_dependencies_tts_stt.py -v
```

Expected: 2 FAILED (both currently use fallback defaults instead of raising).

- [ ] **Step 3: Fix STT fallback in `dependencies.py`**

Find line 142 in `backend/src/dependencies.py`:

```python
    # Before (line 140-142):
    whisper_model = model or "whisper-large-v2"
```

Replace with:

```python
    if not model:
        raise feature_router.FeatureNotConfigured(
            "stt route has no model_name — set it in the admin KI panel"
        )
    whisper_model = model
```

Also update the comment above (lines 139-141) — remove the mention of "sane default":

```python
    # Whisper model name lives in the feature_route's model_name slot.
    whisper_model = model  # (set above, raises FeatureNotConfigured if not configured)
```

Actually just delete those comment lines and replace:

```python
    binding = feature_router.resolve("stt")
    api_key, base_url, model, provider_name = _binding_tuple(binding)
    if not model:
        raise feature_router.FeatureNotConfigured(
            "stt route has no model_name — set it in the admin KI panel"
        )
    return OpenAICompatLLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        provider=provider_name,
        whisper_model=model,
    )
```

- [ ] **Step 4: Fix TTS fallback in `dependencies.py`**

Find line 194 in `backend/src/dependencies.py`:

```python
    # Before:
    model = provider_models.get(str(provider_id)) or (route.get("model_name") if route else None) or "tts-1"
```

Replace with:

```python
    model = provider_models.get(str(provider_id)) or (route.get("model_name") if route else None)
    if not model:
        raise feature_router.FeatureNotConfigured(
            "tts route has no model_name — set it in the admin KI panel"
        )
```

Make sure `feature_router` is imported at the top of the function or module. Check: `dependencies.py` already imports via `from src.services import feature_router` (used in `resolve_whisper_client`). Confirm this import exists before making the change.

- [ ] **Step 5: Run tests — expect PASS**

```bash
docker exec kis-backend python -m pytest tests/test_dependencies_tts_stt.py -v
```

Expected: 2 PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/src/dependencies.py backend/tests/test_dependencies_tts_stt.py
git commit -m "feat: remove whisper-large-v2 and tts-1 fallbacks from dependencies — raise FeatureNotConfigured"
```

---

## Task 4: Make `whisper_model` required in `openai_compat_llm/base.py`

**Files:**
- Modify: `backend/src/services/openai_compat_llm/base.py:64`

After Task 3, `dependencies.py:resolve_whisper_client` always passes `whisper_model=model` (never None). This task removes the default so accidental omission fails loudly.

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_openai_compat_tts.py`:

```python
def test_openai_compat_llm_client_requires_whisper_model():
    """Constructing OpenAICompatLLMClient without whisper_model must raise TypeError."""
    from src.services.openai_compat_llm.base import OpenAICompatLLMClient
    with pytest.raises(TypeError):
        OpenAICompatLLMClient(
            api_key="k",
            base_url="http://example.com",
            model="gpt-4",
            provider="test",
            # whisper_model intentionally omitted
        )
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
docker exec kis-backend python -m pytest tests/test_openai_compat_tts.py::test_openai_compat_llm_client_requires_whisper_model -v
```

Expected: FAILED (currently uses `"whisper-large-v2"` default — no error raised).

- [ ] **Step 3: Remove default in `base.py`**

In `backend/src/services/openai_compat_llm/base.py` line 64, change:

```python
        whisper_model: str = "whisper-large-v2",
```

to:

```python
        whisper_model: str,
```

- [ ] **Step 4: Run all tests — expect PASS**

```bash
docker exec kis-backend python -m pytest tests/test_openai_compat_tts.py -v
```

Expected: all 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/openai_compat_llm/base.py backend/tests/test_openai_compat_tts.py
git commit -m "feat: make whisper_model required in OpenAICompatLLMClient — remove whisper-large-v2 default"
```

---

## Task 5: Fix `feature_route_test.py` — remove `_DEFAULT_TTS_MODEL`, use first DB voice

**Files:**
- Modify: `backend/src/services/feature_route_test.py:84-97,135-148`
- Create: `backend/tests/test_feature_route_test_unit.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_feature_route_test_unit.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
docker exec kis-backend python -m pytest tests/test_feature_route_test_unit.py -v
```

Expected: 3 FAILED (`test_feature_route` doesn't accept `voices=` yet; uses `_DEFAULT_TTS_MODEL`; uses `"alloy"`).

- [ ] **Step 3: Implement changes in `feature_route_test.py`**

**Remove line 84:**
```python
_DEFAULT_TTS_MODEL = "tts-1"
```
(delete it entirely)

**Update `test_feature_route` signature** — add `voices` parameter:

```python
def test_feature_route(
    *,
    feature: str,
    protocol: str,
    base_url: str,
    api_key: Optional[str],
    model_name: Optional[str],
    voices: Optional[list] = None,
) -> FeatureTestResult:
```

**Update the dispatch in `test_feature_route`** to pass `voices` through:

```python
        if protocol == OpenAICompatAdapter.PROTOCOL:
            return _test_openai_compat(
                feature=feature,
                base_url=base_url,
                api_key=api_key,
                model_name=model_name,
                voices=voices or [],
            )
```

**Update `_test_openai_compat` signature** — add `voices`:

```python
def _test_openai_compat(
    *,
    feature: str,
    base_url: str,
    api_key: Optional[str],
    model_name: Optional[str],
    voices: list,
) -> FeatureTestResult:
```

**Replace TTS branch** (lines 96-97) — from:

```python
    if feature == "tts":
        return _post_tts(base_url, api_key, model_name or _DEFAULT_TTS_MODEL)
```

to:

```python
    if feature == "tts":
        if not model_name:
            return FeatureTestResult(status="error", error="model_name_not_set")
        if not voices:
            return FeatureTestResult(status="error", error="no_voices_configured")
        return _post_tts(base_url, api_key, model_name, voices)
```

**Update `_post_tts` signature and body** — add `voices` parameter, replace `"alloy"`:

```python
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker exec kis-backend python -m pytest tests/test_feature_route_test_unit.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/feature_route_test.py backend/tests/test_feature_route_test_unit.py
git commit -m "feat: remove tts-1/alloy defaults from feature_route_test — use first DB voice for TTS probe"
```

---

## Task 6: Pass `voices` from `test_route` endpoint in `providers.py`

**Files:**
- Modify: `backend/src/routes/admin/providers.py:323-329`

- [ ] **Step 1: Update the `test_route` call**

In `backend/src/routes/admin/providers.py`, find the `test_feature_route(...)` call (around line 323). The `provider` dict is already in scope. Update the call to pass `voices`:

```python
    result = test_feature_route(
        feature=feature,
        protocol=provider["protocol"],
        base_url=provider["base_url"],
        api_key=provider.get("api_key"),
        model_name=model_name,
        voices=provider.get("voices") or [],
    )
```

Also remove the stale comment on line 314:
```python
        # Mirror the runtime fallback: per-provider model → global model_name → "tts-1"
```
(delete that comment line)

- [ ] **Step 2: Verify no import changes needed**

`test_feature_route` is already imported at the top of `providers.py`. Confirm with:

```bash
docker exec kis-backend grep -n "from src.services.feature_route_test import" src/routes/admin/providers.py
```

- [ ] **Step 3: Run the full test suite**

```bash
docker exec kis-backend python -m pytest tests/ -q --tb=short
```

Expected: all previously-passing tests still pass; new tests from Tasks 1–5 pass.

- [ ] **Step 4: Commit**

```bash
git add backend/src/routes/admin/providers.py
git commit -m "feat: pass provider voices to test_feature_route in admin test_route endpoint"
```

---

## Task 7: Frontend — i18n + `knownCodes`

**Files:**
- Modify: `frontend/messages/en.json:849`
- Modify: `frontend/messages/de.json:849`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx:385-391`

- [ ] **Step 1: Add `no_voices_configured` to `en.json`**

In `frontend/messages/en.json`, find the `testErrors` block (around line 842):

```json
        "testErrors": {
          "model_name_not_set": "No model name entered",
          "tts_speech_endpoint_not_found": "Not reachable",
          "endpoint_not_found": "Not reachable",
          "auth_rejected": "Not reachable",
          "server_error": "Not reachable",
          "unreachable": "Not reachable",
          "invalid_model": "Not reachable"
        },
```

Add `no_voices_configured` after `invalid_model`:

```json
        "testErrors": {
          "model_name_not_set": "No model name entered",
          "tts_speech_endpoint_not_found": "Not reachable",
          "endpoint_not_found": "Not reachable",
          "auth_rejected": "Not reachable",
          "server_error": "Not reachable",
          "unreachable": "Not reachable",
          "invalid_model": "Not reachable",
          "no_voices_configured": "No voices configured — add at least one voice for this provider"
        },
```

- [ ] **Step 2: Add `no_voices_configured` to `de.json`**

In `frontend/messages/de.json`, find the same `testErrors` block and add:

```json
        "testErrors": {
          "model_name_not_set": "Kein Modellname eingetragen",
          "tts_speech_endpoint_not_found": "Nicht erreichbar",
          "endpoint_not_found": "Nicht erreichbar",
          "auth_rejected": "Nicht erreichbar",
          "server_error": "Nicht erreichbar",
          "unreachable": "Nicht erreichbar",
          "invalid_model": "Nicht erreichbar",
          "no_voices_configured": "Keine Stimmen konfiguriert — füge mindestens eine Stimme für diesen Provider hinzu"
        },
```

- [ ] **Step 3: Add `no_voices_configured` to `knownCodes` in `FeatureRoutingCard.tsx`**

In `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx`, find the `knownCodes` set (around line 385):

```typescript
    const knownCodes = new Set([
      "model_name_not_set",
      "tts_speech_endpoint_not_found",
      "endpoint_not_found",
      "auth_rejected",
      "server_error",
      "unreachable",
    ]);
```

Add `"no_voices_configured"`:

```typescript
    const knownCodes = new Set([
      "model_name_not_set",
      "tts_speech_endpoint_not_found",
      "endpoint_not_found",
      "auth_rejected",
      "server_error",
      "unreachable",
      "no_voices_configured",
    ]);
```

- [ ] **Step 4: Type-check the frontend**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors related to our changes.

- [ ] **Step 5: Commit**

```bash
git add frontend/messages/en.json frontend/messages/de.json \
  "frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx"
git commit -m "feat: add no_voices_configured error translation and knownCodes entry"
```

---

## Task 8: Final integration smoke-test

- [ ] **Step 1: Run full backend test suite**

```bash
docker exec kis-backend python -m pytest tests/ -q --tb=short
```

Expected: all tests pass. (The pre-existing failures in `test_permissions.py` and `test_rbac_dependencies.py` are unrelated — they fail due to a Python 3.11 union type syntax issue in those test files, not in the code under test.)

- [ ] **Step 2: Verify no remaining hardcoded defaults**

```bash
grep -rn "whisper-large-v2\|tts-1\|alloy" backend/src/ | grep -v ".pyc" | grep -v test
```

Expected: no matches (the only remaining `alloy` references should be in test files or comments about the old behavior).

- [ ] **Step 3: Verify `FeatureNotConfigured` is raised on misconfigured TTS provider**

Check that a provider with no model_name configured causes the correct error when its TTS test button is clicked: confirm the test returns `{"status": "error", "error": "model_name_not_set"}`.

- [ ] **Step 4: Final commit (if any cleanup)**

```bash
git add -p  # stage only intentional changes
git commit -m "chore: post-integration cleanup after hardcoded defaults removal"
```
