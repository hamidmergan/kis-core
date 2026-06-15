# Design: AIA Transcript Translation Provider — Admin Configuration

**Date:** 2026-05-28
**Branch:** feat/provider-voice-config (or separate branch)
**Approach:** New `transcript_translate` feature route — single admin-configured provider

## Problem

The AIA (AI Assistant) workspace allows translating a German transcript to English on demand (`POST /regenerate-en-transcript`). The translation provider is currently selected via a hardcoded string setting (`db.get_setting("transcript_translation_provider", "llm")`) with a `"deepl"/"llm"` string dispatch. This bypasses the dynamic feature-routes system used by all other AI features (`stt`, `tts`, `doc_translate`, etc.), is not visible in the admin KI panel, and uses the same ad-hoc pattern being removed elsewhere in the codebase.

---

## Architecture

### New feature route: `transcript_translate`

A new row is added to `FEATURE_ROUTES_DEFAULTS` in `schema.py`. It is a single-provider route (not user-choice): the admin picks one provider in the KI panel; users cannot override it at runtime.

The backend resolves the provider via `feature_router.resolve("transcript_translate")` — the same pattern used by `stt`, `vision`, `image_gen`, etc. The `get_translate_client_for_provider(provider_id)` helper (already committed, `3af0098`) handles the DeepL vs LLM dispatch.

The old `transcript_translation_provider` settings row and `translation_llm_provider` string constant in `schema.py:1082` are left in place (they are legacy rows and removing them risks a migration issue even in dev). The code path that reads them is simply replaced.

---

## Section 1: Backend Changes

### 1.1 `backend/src/core/db/schema.py`

Add `transcript_translate` to `FEATURE_ROUTES_DEFAULTS`:

```python
{"feature": "transcript_translate", "provider_id": None, "model_name": None, "user_choices": [], "provider_models": {}},
```

### 1.2 `backend/src/features/ai_assistant/tasks/ingestion.py`

**`_run_translate_transcript_en_inner`** — change signature from `provider: str` to `provider_id: int | None`:

```python
# Before
def _run_translate_transcript_en_inner(source_uuid: str, provider: str):
    if provider == "llm":
        client = LLMTranslationClient(...)
        ...
    else:
        client = DeepLTranslationClient(...)
        ...

# After
def _run_translate_transcript_en_inner(source_uuid: str, provider_id: int | None):
    client, glossary = get_translate_client_for_provider(provider_id)
    # use client directly — same translation call as before
```

**`run_translate_transcript_en`** Celery task — change signature from `provider: str` to `provider_id: int | None`:

```python
@celery_app.task
def run_translate_transcript_en(source_uuid: str, provider_id: int | None = None):
    _run_translate_transcript_en_inner(source_uuid, provider_id)
```

### 1.3 `backend/src/features/ai_assistant/routes/sources/_streaming.py`

**`regenerate_en_transcript` endpoint** — replace `db.get_setting` + string dispatch with `feature_router.resolve`:

```python
# Before
effective_provider = provider or db.get_setting("transcript_translation_provider", "llm")
if effective_provider not in ("deepl", "llm"):
    raise HTTPException(status_code=400, ...)
run_translate_transcript_en.delay(source_uuid, effective_provider)

# After
from src.services.feature_router import feature_router, FeatureNotConfigured
try:
    binding = feature_router.resolve("transcript_translate")
except FeatureNotConfigured:
    raise HTTPException(status_code=503, detail="transcript_translate not configured — set it in the admin KI panel")
run_translate_transcript_en.delay(source_uuid, binding["provider_id"])
```

The `provider` query parameter that currently allows the caller to override the provider is removed. Provider selection is admin-only.

---

## Section 2: Admin Frontend

### 2.1 `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx`

1. Add `"transcript_translate"` to `FEATURE_ORDER` (after `doc_translate`, before or after `stt` — translation group makes sense)
2. Add `FEATURE_CAPABILITY["transcript_translate"] = "translation"` so only translation-capable providers appear in the dropdown

No change to rendering logic — `transcript_translate` renders as a standard single-provider row (same as `stt`, `ocr`, etc.), not the stacked user-choice style used by `tts`/`doc_translate`.

### 2.2 i18n

**`frontend/messages/en.json`** under `admin.providers.featureLabels`:
```json
"transcript_translate": "Transcript translation"
```

**`frontend/messages/de.json`** under `admin.providers.featureLabels`:
```json
"transcript_translate": "Transkript-Übersetzung"
```

---

## Error Handling

- `feature_router.resolve("transcript_translate")` raises `FeatureNotConfigured` when no provider is set → HTTP 503 with descriptive message
- This surfaces in the AIA workspace as a generic service error, same as other unconfigured features
- No frontend changes needed in the AIA workspace; the existing error display handles 503

---

## Out of Scope

- User-selectable provider in AIA workspace (admin-only config, users don't choose)
- `TranscriptPanel.tsx` changes — no frontend changes needed in the workspace
- Removing the legacy `transcript_translation_provider` and `translation_llm_provider` settings rows from `schema.py:1082` — low-priority cleanup, deferred
- `stt/page.tsx` translation option — the standalone STT tool is a separate flow with no translation step

---

## Files Changed

| File | Change |
|---|---|
| `backend/src/core/db/schema.py` | Add `transcript_translate` to `FEATURE_ROUTES_DEFAULTS` |
| `backend/src/features/ai_assistant/tasks/ingestion.py` | `provider: str` → `provider_id: int \| None`; replace string dispatch with `get_translate_client_for_provider` |
| `backend/src/features/ai_assistant/routes/sources/_streaming.py` | Replace `db.get_setting` + `HTTPException(400)` with `feature_router.resolve` + `HTTPException(503)` |
| `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx` | Add `transcript_translate` to `FEATURE_ORDER` and `FEATURE_CAPABILITY` |
| `frontend/messages/en.json` | Add `featureLabels.transcript_translate` |
| `frontend/messages/de.json` | Add `featureLabels.transcript_translate` |
