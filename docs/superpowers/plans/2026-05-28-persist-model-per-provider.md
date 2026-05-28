# Persist Model Name Per Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Single-provider feature routes (Chat, Embeddings, OCR, STT, Vision, image_gen, image_edit) in the admin UI remember the model name per provider, so switching the provider dropdown restores the model previously entered for that provider.

**Architecture:** Frontend-only change. The DB column `feature_routes.provider_models JSONB` and the backend resolver path (`provider_models[provider_id]` preferred over `model_name`) already exist. We extend the existing per-provider-model write/read pattern (currently used only by multi-provider rows like TTS) to single-provider rows by adjusting two React component files.

**Tech Stack:** Next.js (App Router), React, TypeScript, next-intl. Admin panel under `frontend/src/app/[locale]/admin/_components/providers/`.

**Spec:** `docs/superpowers/specs/2026-05-28-persist-model-per-provider-design.md`

---

## File Structure

Files modified by this plan:

- `frontend/src/app/[locale]/admin/_components/providers/index.tsx` — `onChangeProvider` and `onChangeModel` handlers for `FeatureRoutingCard`. The current `onChangeModel` already overwrites only `model_name`; we extend it to also write `provider_models[provider_id]`. The current `onChangeProvider` discards model context; we make it set `model_name` from the per-provider entry of the newly selected provider so the resolver fallback and post-refresh UI stay aligned.
- `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx` — single-provider `<input>` (last block in `FeatureRow`, around line 324) reads its `defaultValue`/`key` from `provider_models[String(providerId)] ?? model_name` instead of `model_name` alone.

No new files. No backend or DB changes.

---

## Task 1: Display per-provider model in single-provider row

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx:303-336`

The single-provider variant of `FeatureRow` (the final `return` block in the function — the one with `grid-cols-[1fr_180px_220px_auto]`) currently binds the model input to `route?.model_name`. We change it to read the per-provider entry first, falling back to `model_name` for legacy rows.

- [ ] **Step 1: Read current single-provider input block**

Open `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx`. Confirm the block to modify is:

```tsx
      <div className="flex gap-2 sm:contents">
        <select
          value={providerId ?? ""}
          onChange={(e) => onChangeProvider(e.target.value ? Number(e.target.value) : null)}
          disabled={eligible.length === 0}
          className="flex-1 min-w-0 text-xs px-2 py-1.5 border-2 border-border rounded-md hover:border-kb focus:outline-none focus:border-kb bg-background disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <option value="">{t("routes.unselected")}</option>
          {eligible.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <input
          key={route?.model_name ?? ""}
          type="text"
          defaultValue={route?.model_name ?? ""}
          onBlur={(e) => onChangeModel(e.target.value.trim() || null)}
          disabled={!provider}
          placeholder={provider ? t("routes.modelPlaceholder") : "—"}
          spellCheck={false}
          className="text-xs px-2 py-1.5 border-2 border-border rounded-md font-mono hover:border-kb focus:outline-none focus:border-kb bg-background disabled:opacity-60 disabled:cursor-not-allowed"
        />
        <TestButton state={testState} disabled={!canTest} onClick={onTest} />
      </div>
```

Verify by reading the file (no edit yet).

- [ ] **Step 2: Replace the `<input>` `key`/`defaultValue` source**

Replace the `<input>` element above with this version (only the two `key`/`defaultValue` lines change):

```tsx
        <input
          key={(providerId != null ? route?.provider_models?.[String(providerId)] : null) ?? route?.model_name ?? ""}
          type="text"
          defaultValue={(providerId != null ? route?.provider_models?.[String(providerId)] : null) ?? route?.model_name ?? ""}
          onBlur={(e) => onChangeModel(e.target.value.trim() || null)}
          disabled={!provider}
          placeholder={provider ? t("routes.modelPlaceholder") : "—"}
          spellCheck={false}
          className="text-xs px-2 py-1.5 border-2 border-border rounded-md font-mono hover:border-kb focus:outline-none focus:border-kb bg-background disabled:opacity-60 disabled:cursor-not-allowed"
        />
```

Note: `route?.provider_models` is already typed as `Record<string, string>` in `_types.ts:63`, so no new typing is needed. `providerId` is already in scope (computed at the top of `FeatureRow` from `route?.provider_id`).

- [ ] **Step 3: Type check**

Run from repo root:

```bash
cd frontend && npm run typecheck
```

Expected: no new errors. (If the repo uses a different command, use `npx tsc --noEmit` from `frontend/`.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx
git commit -m "feat(admin): read model from provider_models in single-provider row"
```

---

## Task 2: Persist edits under `provider_models[provider_id]`

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/index.tsx:126-139`

The current `onChangeModel` writes only `model_name`. We extend it to also write under `provider_models[String(providerId)]`, deleting the key when the new value is null/empty.

- [ ] **Step 1: Read current `onChangeModel`**

Open `frontend/src/app/[locale]/admin/_components/providers/index.tsx`. Confirm lines 126-139 are:

```tsx
  const onChangeModel = useCallback(
    async (feature: Feature, modelName: string | null) => {
      const existing = routes.find((r) => r.feature === feature);
      if (!existing?.provider_id) return;
      await setFeatureRoute(feature, {
        provider_id: existing.provider_id,
        model_name: modelName,
        user_choices: existing.user_choices ?? null,
        provider_models: existing.provider_models,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );
```

- [ ] **Step 2: Replace `onChangeModel` body**

Replace with:

```tsx
  const onChangeModel = useCallback(
    async (feature: Feature, modelName: string | null) => {
      const existing = routes.find((r) => r.feature === feature);
      if (!existing?.provider_id) return;
      const nextProviderModels = { ...(existing.provider_models ?? {}) };
      const key = String(existing.provider_id);
      if (modelName) {
        nextProviderModels[key] = modelName;
      } else {
        delete nextProviderModels[key];
      }
      await setFeatureRoute(feature, {
        provider_id: existing.provider_id,
        model_name: modelName,
        user_choices: existing.user_choices ?? null,
        provider_models: nextProviderModels,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );
```

- [ ] **Step 3: Type check**

```bash
cd frontend && npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/[locale]/admin/_components/providers/index.tsx
git commit -m "feat(admin): persist single-provider model edits under provider_models"
```

---

## Task 3: Sync `model_name` from `provider_models` on provider change

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/index.tsx:113-124`

When the user changes provider in a single-provider row, the backend resolver's fallback (`provider_models[provider_id] ?? model_name`) and the post-refresh display should both point at whatever model was previously saved for the newly selected provider. Today `onChangeProvider` carries forward the old `model_name`, which then leaks across providers until the user types something else.

- [ ] **Step 1: Read current `onChangeProvider`**

Confirm lines 113-124 of `frontend/src/app/[locale]/admin/_components/providers/index.tsx` are:

```tsx
  const onChangeProvider = useCallback(
    async (feature: Feature, providerId: number | null) => {
      const existing = routes.find((r) => r.feature === feature);
      await setFeatureRoute(feature, {
        provider_id: providerId,
        model_name: providerId ? existing?.model_name ?? null : null,
        user_choices: existing?.user_choices ?? null,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );
```

- [ ] **Step 2: Replace `onChangeProvider` body**

Replace with:

```tsx
  const onChangeProvider = useCallback(
    async (feature: Feature, providerId: number | null) => {
      const existing = routes.find((r) => r.feature === feature);
      const carriedModel =
        providerId != null
          ? existing?.provider_models?.[String(providerId)] ?? null
          : null;
      await setFeatureRoute(feature, {
        provider_id: providerId,
        model_name: carriedModel,
        user_choices: existing?.user_choices ?? null,
        provider_models: existing?.provider_models,
      });
      await refreshAll();
    },
    [routes, refreshAll],
  );
```

Notes:
- `provider_models` is forwarded unchanged so existing entries for other providers are preserved.
- When `providerId == null` (deselect), `model_name` becomes `null` — same as before.

- [ ] **Step 3: Type check**

```bash
cd frontend && npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/[locale]/admin/_components/providers/index.tsx
git commit -m "feat(admin): restore per-provider model on provider switch"
```

---

## Task 4: Manual verification in admin panel

**Files:** (none modified)

The behavior is admin-UI driven and not covered by automated frontend tests in this codebase. Verify manually against the running app per the spec's verification section.

- [ ] **Step 1: Start the app**

From repo root:

```bash
docker compose up -d
```

(If a different start command is canonical for this repo, use that — check `README.md` or `docker-compose.yml`.) Wait for the frontend container to report ready.

- [ ] **Step 2: Open the admin providers tab**

Navigate to `http://localhost:3000/de/admin` (or whichever host the app uses) → Provider/Funktionen section. Confirm at least two providers exist that both have the `chat` capability (e.g., KISSKI and THL myLab). If not, create a second one via the existing provider dialog.

- [ ] **Step 3: Verify per-provider persistence (golden path)**

1. Select Chat → Provider = KISSKI, type model name `chat-xlarge`, blur the input.
2. Switch Chat dropdown to THL myLab. Expected: model input becomes empty (no prior value for THL myLab).
3. Type `llama3-70b`, blur.
4. Switch back to KISSKI. Expected: model input shows `chat-xlarge`.
5. Switch back to THL myLab. Expected: model input shows `llama3-70b`.
6. Hard-reload the page (Cmd-Shift-R). Repeat steps 4-5. Expected: values still restored from the DB.

- [ ] **Step 4: Verify one other single-provider feature**

Repeat steps 3.1-3.5 with the **Embeddings** row (or any other enabled single-provider feature with two eligible providers). Same expectation.

- [ ] **Step 5: Verify multi-provider rows are unchanged**

Open the TTS row. Confirm each provider still has its own model input and the values you previously saved (per the screenshot, `xtts-v2` for THL myLab) are still present. Edit one of them, blur, reload — value should persist.

- [ ] **Step 6: Verify provider-deselect still clears model**

In the Chat row, set the provider dropdown back to `— Anbieter wählen —`. Reload. Re-select KISSKI. Expected: model field shows `chat-xlarge` again (the entry under `provider_models["<kisski_id>"]` survives deselect).

- [ ] **Step 7: Report verification result**

If all steps pass, report success in your turn-end summary. If any step fails, surface the exact failing step and stop — do not claim completion.

---

## Self-Review Notes

- **Spec coverage:** Display change → Task 1. `onChangeModel` write → Task 2. `onChangeProvider` carry-over → Task 3. Verification checklist from spec → Task 4. Edge cases (typing-then-switching, deselect, provider-loses-capability, provider-deletion) are either covered by Task 4 step 6, or already handled in unchanged backend code as noted in the spec.
- **No backend tasks:** spec explicitly excludes backend/DB; resolver already handles `provider_models` preference.
- **No tests added:** existing admin/providers tests live on the backend side (route shape, repository), and the change here is purely UI wiring. Manual verification covers it; adding React component tests for this would be out of scope for the codebase's current testing convention.
