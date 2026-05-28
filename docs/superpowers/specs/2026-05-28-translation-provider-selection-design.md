# Translation Provider Selection — Design Spec

**Date:** 2026-05-28
**Features:** Dokumenten-Übersetzung (`doc_translate`), Screencast-Übersetzung (`screencast_translate`)

## Overview

Both translation features share a single provider configuration. The admin configures eligible translation providers once; users pick which provider to use in each tool at runtime via a dropdown — identical to how TTS works.

---

## Architecture

### Single feature route for both tools

`doc_translate` is the canonical feature route for all translation. `screencast_translate` is kept as a routing label in the backend but resolves from the same `doc_translate` configuration. The admin panel shows only one "Übersetzung" row.

### Data model (no schema changes)

`feature_routes` row for `doc_translate`:
- `user_choices: [providerId, ...]` — which providers the user may pick from
- `provider_models: {"42": "mistral-small", ...}` — optional model name per provider
- `provider_id` / `model_name` — unused for user-choice features (kept as null)

---

## Admin Panel

**File:** `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx`

### Changes

1. Extend the TTS-style branch condition from `feature === "tts"` to `feature === "tts" || feature === "doc_translate"`. This renders stacked provider rows (label + model input + test button) for both TTS and translation.

2. Remove `"screencast_translate"` from `FEATURE_ORDER`. It no longer needs its own admin row.

3. The existing `onChangeProviderModel` / `onTestProvider` handlers in `index.tsx` already work correctly for any feature — no changes needed there.

### Result

Admin sees one "Übersetzung" row with one sub-row per eligible provider (e.g., KISSKI, THL myLab), each with an optional model name field and a test button.

---

## Backend

### New endpoint: `GET /translate/providers`

**File:** `backend/src/routes/translate.py`

Returns the list of enabled providers from `doc_translate.user_choices`, including their id, name, and whether they require a model name. Mirrors the shape of `GET /tts/providers-with-voices` (without the voices field).

```
Response: { "providers": [{ "id": int, "name": str }] }
```

Empty list → tools hide the provider dropdown and fall back to a single configured provider.

### Modified task: `run_translate`

**File:** `backend/src/tasks/general_tasks.py`

- Accept `provider_id: int | None = None` instead of `translation_provider: str`
- Resolve via `feature_router.resolve("doc_translate", user_provider_id=provider_id)`
- Use `make_translation_adapter(binding)` — already handles both DeepL and LLM protocols
- Remove the old `effective_provider` string-dispatch logic

### Modified route: `POST /translate`

**File:** `backend/src/routes/translate.py`

- Accept `provider_id: int | None = Form(None)` instead of `translation_provider: str`
- Remove `GET /translate/config` (hardcoded deepl/llm — replaced by new providers endpoint)

### Modified route: `POST /screencast/translate`

**File:** `backend/src/routes/screencast/translate.py`

- Accept `provider_id: int | None = Form(None)`
- Store it in `queue_params.json`
- Worker passes `provider_id` to the translation step, which resolves via `resolve("doc_translate", user_provider_id=provider_id)`

---

## Frontend Tool UIs

### Dokumenten-Übersetzung — `/tools/translate/page.tsx`

1. On mount: `GET /translate/providers` → store provider list
2. If `providers.length > 1`: render a provider `<select>` (same pattern as TTS page)
3. Send `provider_id: number` as FormData field instead of `translation_provider: string`

### Screencast-Upload-Schritt

**File:** TBD — the component that renders the upload/configure step of the screencast tool

1. On mount (or when step becomes visible): `GET /translate/providers`
2. Show provider dropdown when >1 providers
3. Include `provider_id` in the form submission that triggers screencast processing

---

## Error Handling

- `providers.length === 0`: hide dropdown, submit without `provider_id` — backend falls back to the first available translation provider or returns a clear "not configured" error
- Backend `FeatureNotConfigured` → HTTP 503 with localized error message (existing pattern)

---

## Out of Scope

- Voice selection for translation (not applicable)
- Per-language provider routing
- Merging the `screencast_translate` DB row into `doc_translate` (two rows remain, screencast row is unused/ignored)
