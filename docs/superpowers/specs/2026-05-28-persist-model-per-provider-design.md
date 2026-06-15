# Persist Model Name Per Provider in Single-Provider Feature Routes

## Problem

In the admin "Funktionen" routing UI, single-provider features (Chat, Embeddings, OCR, STT, Vision, image_gen, image_edit) store only one global `model_name` per feature route. When the admin switches the provider via the dropdown, the model field keeps showing the previous provider's model — they have to re-enter it every time. Switching back loses the previous value entirely.

Multi-provider features (TTS, doc_translate, transcript_translate) already store per-provider models in `feature_routes.provider_models` (JSONB). The single-provider rows just don't use that column yet.

## Goal

Each (feature, provider) pair remembers its last entered model name. Switching providers in a single-provider row restores the model name previously saved for the newly selected provider.

## Non-Goals

- No backend changes. The resolver in `backend/src/services/feature_router.py:74-75` already prefers `provider_models[provider_id]` over `model_name`.
- No DB migration of existing routes. Legacy rows keep working via the `model_name` fallback path and migrate organically the next time the admin saves a model.
- No changes to multi-provider rows — they already follow the desired pattern.
- No cleanup of stale `provider_models` entries when a provider loses a capability. They are inert and don't affect rendering.

## Behavior

### Display value for the model input (single-provider row)

```
provider_models[current_provider_id] ?? model_name ?? ""
```

This makes the display always reflect what was last saved for the currently selected provider. The `model_name` fallback covers routes saved before this change is deployed.

### `onChangeModel(feature, newModel)` (single-provider row)

Precondition: `existing.provider_id != null` (unchanged from today).

Payload sent to `setFeatureRoute`:

- `provider_id`: existing.provider_id (unchanged)
- `model_name`: `newModel` — mirrored to the global field as a safety net for any caller that still reads `model_name` directly
- `user_choices`: existing.user_choices ?? null (unchanged)
- `provider_models`: `{ ...existing.provider_models, [String(provider_id)]: newModel }` when `newModel` is set; with the key removed when `newModel` is null/empty

### `onChangeProvider(feature, newProviderId)`

When `newProviderId != null`:

- `provider_id`: `newProviderId`
- `model_name`: `existing.provider_models[String(newProviderId)] ?? null` — so the resolver's fallback path matches what the UI will show after refresh
- `user_choices`: existing.user_choices ?? null (unchanged)
- `provider_models`: `existing.provider_models` (unchanged — preserves every previously entered model)

When `newProviderId == null` (deselect):

- `provider_id`: `null`
- `model_name`: `null`
- `user_choices`: existing.user_choices ?? null
- `provider_models`: existing.provider_models (unchanged)

### Multi-provider rows

No behavior change. `onChangeProviderModel` already writes per-provider entries, and `onChangeProvider` is not invoked for those rows.

## Edge Cases

- **"Type then switch provider" race**: native input blur fires before the select's onChange, so the typed value is saved under the old `provider_id` first, then the provider change fires with the new id. Same mechanism already in use for multi-provider rows. Works as desired.
- **Provider deletion**: `backend/src/features/ai_providers/repository/feature_routes.py:158-163` already strips the deleted provider's entry from every route's `provider_models`. No change needed.
- **Provider loses a capability later**: a stale entry remains in `provider_models` but is never displayed (the row's eligible-providers filter hides it). Inert, no cleanup needed.
- **Empty input → null**: clearing the model field deletes the entry from `provider_models` (rather than storing an empty string). Matches existing multi-provider behavior in `FeatureRoutingCard.tsx:225`.

## Files Changed

- `frontend/src/app/[locale]/admin/_components/providers/index.tsx`
  - `onChangeProvider`: include `provider_models` in payload (unchanged), set `model_name` from `existing.provider_models[String(providerId)] ?? null`.
  - `onChangeModel`: also write `provider_models[String(existing.provider_id)] = modelName` (or delete the key when `modelName` is null/empty).

- `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx`
  - Single-provider `<input>` (around line 324): `defaultValue` and `key` derived from `route?.provider_models?.[String(providerId)] ?? route?.model_name ?? ""` instead of `route?.model_name ?? ""`.

## Verification

- Manual test in admin panel:
  1. Set Chat = KISSKI, model "chat-xlarge". Save (blur).
  2. Switch dropdown to THL myLab, enter model "llama3-70b". Save.
  3. Switch back to KISSKI → model field shows "chat-xlarge".
  4. Switch back to THL myLab → model field shows "llama3-70b".
  5. Reload page → both values still restored on switch.
- Repeat the test for at least one other single-provider feature (e.g., OCR or Embeddings).
- Confirm TTS row still works unchanged (multi-provider editor).
- Run frontend type check and existing admin/provider tests.
