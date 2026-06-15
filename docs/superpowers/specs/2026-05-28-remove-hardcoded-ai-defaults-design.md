# Design: Remove Hardcoded AI Defaults

**Date:** 2026-05-28
**Branch:** feat/remove-hardcoded-ai-defaults (to be created)
**Approach:** Option A — Fail-fast (no silent fallbacks)

## Problem

Several hardcoded AI default values bypass the admin KI panel, causing silent wrong behavior when providers like Kokoro or myLab use different model names or voice IDs than the OpenAI defaults:

| Location | Hardcoded value | Effect |
|---|---|---|
| `dependencies.py:141` | `"whisper-large-v2"` | Wrong STT model silently used |
| `dependencies.py:193` | `"tts-1"` | Wrong TTS model silently used |
| `openai_compat_tts.py:14–15` | `_DEFAULT_MODEL = "tts-1"`, `_DEFAULT_VOICE = "alloy"` | Wrong TTS model/voice silently used |
| `openai_compat_llm/base.py:64` | `whisper_model="whisper-large-v2"` | Wrong STT model silently used |
| `feature_route_test.py:84,97,139` | `"tts-1"`, `"alloy"` | Test uses wrong model/voice |

## Approach: Fail-fast

Remove all fallbacks. When a required value is not configured, raise `FeatureNotConfigured` with a descriptive message pointing the admin to the KI panel. This extends the existing pattern already used for `image_gen`, `vision`, and `image_edit`.

No new abstractions. No config flags. No gradual migration. Just remove the constants and let the missing values surface immediately.

---

## Section 1: Backend Changes

### 1.1 `backend/src/services/openai_compat_tts.py`

- Remove `_DEFAULT_VOICE = "alloy"` (line 14)
- Remove `_DEFAULT_MODEL = "tts-1"` (line 15)
- Make `model` parameter required (remove default in `__init__`)
- Line 105: replace `voice = _DEFAULT_VOICE if voice_id in ("default", "") else voice_id` with:
  ```python
  if not voice_id or voice_id == "default":
      raise ValueError("voice_id must be set — configure voices for this provider in the admin KI panel")
  voice = voice_id
  ```

### 1.2 `backend/src/dependencies.py`

**STT (line 141):**
```python
# Before
whisper_model = model or "whisper-large-v2"

# After
if not model:
    raise FeatureNotConfigured("stt route has no model_name — set it in the admin KI panel")
whisper_model = model
```

**TTS (line 193):**
```python
# Before
model = provider_models.get(str(provider_id)) or (route.get("model_name") if route else None) or "tts-1"

# After
model = provider_models.get(str(provider_id)) or (route.get("model_name") if route else None)
if not model:
    raise FeatureNotConfigured("tts route has no model_name — set it in the admin KI panel")
```

### 1.3 `backend/src/services/openai_compat_llm/base.py`

- Line 64: change `whisper_model: str = "whisper-large-v2"` to `whisper_model: str` (required parameter)
- All call sites in `dependencies.py` already pass the model from the route — no other callers affected.

### 1.4 `backend/src/services/feature_route_test.py`

- Remove `_DEFAULT_TTS_MODEL = "tts-1"` (line 84)
- Line 97: change `return _post_tts(base_url, api_key, model_name or _DEFAULT_TTS_MODEL)` to:
  ```python
  if not model_name:
      return FeatureTestResult(status="error", error="model_name_not_set")
  return _post_tts(base_url, api_key, model_name, voices=voices)
  ```
- `_post_tts` signature: add `voices: list` parameter. Replace `"alloy"` with:
  ```python
  if not voices:
      return FeatureTestResult(status="error", error="no_voices_configured")
  voice_id = voices[0]["voice_id"]
  ```

### 1.5 `backend/src/routes/admin/providers.py` — `test_route` endpoint

The `provider` dict is already loaded in this endpoint. Pass `provider.get("voices", [])` through `test_feature_route()` to `_post_tts()`:

```python
result = test_feature_route(
    feature=feature,
    protocol=protocol,
    base_url=base_url,
    api_key=api_key,
    model_name=model_name,
    voices=provider.get("voices", []),  # new
)
```

---

## Section 2: Error Messages / i18n + Frontend

### New test error code: `no_voices_configured`

**`FeatureRoutingCard.tsx` — `TestStatusLine` known codes** (already handles `model_name_not_set`):

Add `"no_voices_configured"` to the `knownCodes` set.

**`frontend/messages/en.json`** under `admin.providers.routes.testErrors`:
```json
"no_voices_configured": "No voices configured — add at least one voice for this provider"
```

**`frontend/messages/de.json`** under `admin.providers.routes.testErrors`:
```json
"no_voices_configured": "Keine Stimmen konfiguriert — füge mindestens eine Stimme für diesen Provider hinzu"
```

### Runtime errors (`FeatureNotConfigured`)

These surface as HTTP 503 at the chat/STT/TTS endpoints and are already handled by the frontend as `service_unavailable`. No frontend changes required beyond the test error code above.

---

## Out of Scope

- `FEATURE_ORDER`, `FEATURE_CAPABILITY`, `FEATURE_EXTRA_CAPABILITIES` in `FeatureRoutingCard.tsx` — frontend duplicates of backend constants. Low-priority maintenance issue, not addressed here.
- Probe capabilities in `openai_compat.py` — intentionally suggests all capabilities on successful probe; admin deselects what doesn't apply. No change.

---

## Files Changed

| File | Change |
|---|---|
| `backend/src/services/openai_compat_tts.py` | Remove `_DEFAULT_VOICE`, `_DEFAULT_MODEL`; make `model` required; raise on empty `voice_id` |
| `backend/src/dependencies.py` | Remove `"whisper-large-v2"` and `"tts-1"` fallbacks; raise `FeatureNotConfigured` |
| `backend/src/services/openai_compat_llm/base.py` | Make `whisper_model` required |
| `backend/src/services/feature_route_test.py` | Remove `_DEFAULT_TTS_MODEL`; add `voices` param to `_post_tts`; new error `no_voices_configured` |
| `backend/src/routes/admin/providers.py` | Pass `voices` to `test_feature_route()` |
| `frontend/messages/en.json` | Add `no_voices_configured` error string |
| `frontend/messages/de.json` | Add `no_voices_configured` error string |
| `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx` | Add `no_voices_configured` to `knownCodes` |
