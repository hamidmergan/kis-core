# Admin Providers — Export/Import Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the top-level Export and Import buttons in the Admin Provider tab with a single kebab-menu entry that opens a two-tab modal (Export, Import). The Export tab adds per-provider selection with client-side filtering. Spec: [`docs/superpowers/specs/2026-05-28-admin-providers-export-import-modal-design.md`](../specs/2026-05-28-admin-providers-export-import-modal-design.md).

**Architecture:** New React client component `ExportImportDialog.tsx` housing both tabs and their state. The parent (`providers/index.tsx`) keeps network calls and side-effects behind callback props. A pure helper `filterExportConfig()` does the client-side filter on parsed JSON. The existing `ImportPreviewDialog.tsx` is removed and its preview-render logic moves into the modal's Import tab.

**Tech Stack:** Next.js App Router (client component, `"use client"`), React 18 hooks, `next-intl` for i18n, `@phosphor-icons/react`, Tailwind utility classes. No frontend test harness exists in this codebase — verification is `npx tsc --noEmit` plus manual browser verification.

**Notes on conventions:**
- Files live under `frontend/src/app/[locale]/admin/_components/providers/`.
- Esc + click-outside pattern: see `ImportPreviewDialog.tsx` (current) and `ProviderFormDialog.tsx`.
- i18n keys nest under `admin.providers.*` in both `frontend/messages/de.json` and `frontend/messages/en.json` — strings MUST be added to both files in the same task.
- Use markdown file links with line ranges when referencing existing code.

---

### Task 1: Add i18n strings for the new modal

**Files:**
- Modify: `frontend/messages/de.json` (block `admin.providers.exportImport`, lines 951–979 today)
- Modify: `frontend/messages/en.json` (same block)

- [ ] **Step 1: Add menu-item string under `admin.providers.list`**

In `de.json`, locate the `"list"` block under `admin.providers` (search for `"list": {` inside the `providers` block) and append a `exportImportMenuItem` key:

```json
        "exportImportMenuItem": "Export / Import…",
```

In `en.json`, the same:

```json
        "exportImportMenuItem": "Export / Import…",
```

Place it next to `add`, `emptyTitle`, `emptyHint` — wherever those live in the `list` block.

- [ ] **Step 2: Extend `exportImport` block with modal + export/import sub-keys**

In `de.json`, in the `exportImport` block (currently has `exportButton`, `importButton`, `exportHint`, `preview {…}`, `importSuccessToast`, `errors {…}`), add a `modal`, `export`, and `import` sub-block. Final shape (only the additions shown — keep `exportHint` and the existing `preview` and `errors` blocks as-is):

```json
      "exportImport": {
        "exportButton": "Exportieren",
        "importButton": "Importieren",
        "exportHint": "Die exportierte Datei enthält KEINE API-Keys — diese müssen auf dem Zielsystem manuell neu gesetzt werden.",
        "modal": {
          "title": "Export / Import",
          "tabExport": "Exportieren",
          "tabImport": "Importieren",
          "cancel": "Abbrechen"
        },
        "export": {
          "providersHeading": "Provider",
          "selectAll": "Alle",
          "selectNone": "Keine",
          "selectedCount": "{selected} von {total}",
          "confirmButton": "Exportieren ({count})"
        },
        "import": {
          "dropzoneHint": "JSON-Datei hier ablegen oder klicken zum Auswählen",
          "chooseAnotherFile": "Andere Datei wählen",
          "confirmButton": "Import bestätigen"
        },
        "preview": { "...": "...unchanged..." },
        "importSuccessToast": "...unchanged...",
        "errors": { "...": "...unchanged..." }
      },
```

In `en.json`, the English equivalents:

```json
        "modal": {
          "title": "Export / Import",
          "tabExport": "Export",
          "tabImport": "Import",
          "cancel": "Cancel"
        },
        "export": {
          "providersHeading": "Providers",
          "selectAll": "All",
          "selectNone": "None",
          "selectedCount": "{selected} of {total}",
          "confirmButton": "Export ({count})"
        },
        "import": {
          "dropzoneHint": "Drop a JSON file here or click to select",
          "chooseAnotherFile": "Choose another file",
          "confirmButton": "Confirm import"
        },
```

Leave `exportButton`, `importButton`, `exportHint`, `preview`, `importSuccessToast`, and `errors` blocks untouched. `importSuccessToast` stays (will be removed in Task 6 — keep it now to make i18n diffs reviewable per task).

- [ ] **Step 3: Verify TypeScript still type-checks**

Run from the repo root:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no output (clean exit). next-intl validates keys at usage sites; new keys don't break anything until referenced.

- [ ] **Step 4: Commit**

```bash
git add frontend/messages/de.json frontend/messages/en.json
git commit -m "i18n(admin): add export/import modal strings"
```

---

### Task 2: Add `fetchExportConfig` API helper that returns parsed JSON

Why: the existing `exportConfig()` returns a `Blob` for direct download. The dialog needs the parsed object so it can filter client-side, then re-serialize. A second helper keeps both call sites simple.

**Files:**
- Modify: [`frontend/src/app/[locale]/admin/_components/providers/_api.ts`](../../../frontend/src/app/[locale]/admin/_components/providers/_api.ts) — append a new function near the existing `exportConfig` (around line 167).

- [ ] **Step 1: Add the new helper**

Append after the existing `exportConfig` function (after line 177):

```typescript
export async function fetchExportConfig(): Promise<{ config: unknown; filename: string }> {
  const res = await fetch(`${BASE}/providers/export`, { credentials: "include" });
  if (!res.ok) {
    throw new Error((await res.text()) || `HTTP ${res.status}`);
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match ? match[1] : `kis-ai-config-${new Date().toISOString().slice(0, 10)}.json`;
  const config = await res.json();
  return { config, filename };
}
```

Keep `exportConfig()` (Blob variant) in place for now — it will be removed in Task 6 once nothing references it.

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/_api.ts
git commit -m "feat(admin): add fetchExportConfig helper that returns parsed JSON"
```

---

### Task 3: Add pure `filterExportConfig` helper

A pure function so the dialog's filter rule is isolated and testable later. Lives in its own file because the typed shape of an export-JSON differs from `Provider`/`FeatureRoute` (Backend keys by name, not ID — see [`backend/src/routes/admin/providers.py:424`](../../../backend/src/routes/admin/providers.py#L424)).

**Files:**
- Create: `frontend/src/app/[locale]/admin/_components/providers/_exportFilter.ts`

- [ ] **Step 1: Create the helper**

```typescript
// Shape of an exported JSON (subset we touch). Backend keys cross-refs by
// provider name, so the filter operates on names too.
type ExportedProvider = { name: string; [key: string]: unknown };
type ExportedRoute = {
  feature: string;
  provider_name: string | null;
  model_name: string | null;
  user_choices: string[];
  provider_models: Record<string, string>;
  [key: string]: unknown;
};
type ExportedConfig = {
  providers: ExportedProvider[];
  feature_routes: ExportedRoute[];
  [key: string]: unknown;
};

function isExportedConfig(value: unknown): value is ExportedConfig {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return Array.isArray(v.providers) && Array.isArray(v.feature_routes);
}

/**
 * Keep only providers whose `name` is in `selectedNames`. For each route:
 * - drop the route if its `provider_name` is not selected;
 * - otherwise filter `user_choices` and `provider_models` keys to selected names.
 * Top-level fields (schema_version, exported_at, exported_from) pass through.
 */
export function filterExportConfig(
  config: unknown,
  selectedNames: Set<string>,
): unknown {
  if (!isExportedConfig(config)) return config;
  const providers = config.providers.filter((p) => selectedNames.has(p.name));
  const feature_routes = config.feature_routes
    .filter((r) => r.provider_name !== null && selectedNames.has(r.provider_name))
    .map((r) => ({
      ...r,
      user_choices: (r.user_choices ?? []).filter((n) => selectedNames.has(n)),
      provider_models: Object.fromEntries(
        Object.entries(r.provider_models ?? {}).filter(([name]) =>
          selectedNames.has(name),
        ),
      ),
    }));
  return { ...config, providers, feature_routes };
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/_exportFilter.ts
git commit -m "feat(admin): add filterExportConfig helper for client-side filtering"
```

---

### Task 4: Create `ExportImportDialog` — modal shell + tabs

**Files:**
- Create: `frontend/src/app/[locale]/admin/_components/providers/ExportImportDialog.tsx`

This task creates the dialog skeleton (modal frame, tab bar, Esc/click-outside, prop types) with empty tab bodies. Tabs are wired in Tasks 5 and 6 to land smaller diffs.

- [ ] **Step 1: Create the file**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import type { ImportPreviewResult, Provider } from "./_types";

type Tab = "export" | "import";

type Props = {
  providers: Provider[];
  initialTab: Tab;
  onClose: () => void;
  onExportDownload: (filteredConfig: unknown, filename: string) => void;
  onImportPreview: (config: unknown) => Promise<ImportPreviewResult>;
  onImportConfirm: (config: unknown) => Promise<void>;
};

export default function ExportImportDialog({
  providers,
  initialTab,
  onClose,
  onExportDownload,
  onImportPreview,
  onImportConfirm,
}: Props) {
  const t = useTranslations("admin.providers.exportImport");
  const [tab, setTab] = useState<Tab>(initialTab);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, submitting]);

  const handleBackdropClick = () => {
    if (!submitting) onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-background border border-border-soft rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-5 border-b border-border-soft flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground">{t("modal.title")}</h2>
        </div>

        <div className="px-5 pt-3 border-b border-border-soft flex gap-1">
          <TabButton active={tab === "export"} onClick={() => setTab("export")}>
            {t("modal.tabExport")}
          </TabButton>
          <TabButton active={tab === "import"} onClick={() => setTab("import")}>
            {t("modal.tabImport")}
          </TabButton>
        </div>

        {tab === "export" ? (
          <ExportTab
            providers={providers}
            onCancel={onClose}
            onDownload={onExportDownload}
          />
        ) : (
          <ImportTab
            onCancel={onClose}
            onPreview={onImportPreview}
            onConfirm={onImportConfirm}
            setSubmitting={setSubmitting}
          />
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const base = "px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors";
  const stateClass = active
    ? "border-kb text-foreground"
    : "border-transparent text-muted hover:text-foreground";
  return (
    <button type="button" onClick={onClick} className={`${base} ${stateClass}`}>
      {children}
    </button>
  );
}

// Placeholder bodies — filled in Tasks 5 and 6.
function ExportTab(_: {
  providers: Provider[];
  onCancel: () => void;
  onDownload: (config: unknown, filename: string) => void;
}) {
  return <div className="p-5 text-sm text-muted">Export tab — implemented in Task 5</div>;
}

function ImportTab(_: {
  onCancel: () => void;
  onPreview: (config: unknown) => Promise<ImportPreviewResult>;
  onConfirm: (config: unknown) => Promise<void>;
  setSubmitting: (v: boolean) => void;
}) {
  return <div className="p-5 text-sm text-muted">Import tab — implemented in Task 6</div>;
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/ExportImportDialog.tsx
git commit -m "feat(admin): scaffold ExportImportDialog modal with tab shell"
```

---

### Task 5: Implement Export tab

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/ExportImportDialog.tsx` — replace the placeholder `ExportTab` function.

- [ ] **Step 1: Replace imports + ExportTab body**

At the top of the file, extend the imports:

```tsx
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Warning } from "@phosphor-icons/react";
import { filterExportConfig } from "./_exportFilter";
import { fetchExportConfig } from "./_api";
import type { ImportPreviewResult, Provider } from "./_types";
```

Replace the placeholder `function ExportTab(...)` with:

```tsx
function ExportTab({
  providers,
  onCancel,
  onDownload,
}: {
  providers: Provider[];
  onCancel: () => void;
  onDownload: (config: unknown, filename: string) => void;
}) {
  const t = useTranslations("admin.providers.exportImport");
  const allNames = useMemo(() => providers.map((p) => p.name), [providers]);
  const [selected, setSelected] = useState<Set<string>>(() => new Set(allNames));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const total = allNames.length;
  const count = selected.size;
  const allSelected = count === total;

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(allNames));
  };
  const toggleOne = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const handleExport = async () => {
    setBusy(true);
    setError(null);
    try {
      const { config, filename } = await fetchExportConfig();
      const filtered = filterExportConfig(config, selected);
      onDownload(filtered, filename);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="p-5 space-y-5">
        <div className="text-[12px] text-amber-700 dark:text-amber-400 border-l-2 border-amber-500 pl-2 flex items-start gap-1">
          <Warning size={14} weight="bold" className="mt-0.5 shrink-0" />
          <span>{t("exportHint")}</span>
        </div>

        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
              {t("export.providersHeading")}
            </h3>
            <div className="text-xs text-muted flex items-center gap-2">
              <span>{t("export.selectedCount", { selected: count, total })}</span>
              <span aria-hidden="true">·</span>
              <button
                type="button"
                onClick={toggleAll}
                className="text-kb hover:underline"
              >
                {allSelected ? t("export.selectNone") : t("export.selectAll")}
              </button>
            </div>
          </div>
          <ul className="space-y-1.5">
            {providers.map((p) => (
              <li key={p.name}>
                <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selected.has(p.name)}
                    onChange={() => toggleOne(p.name)}
                    className="accent-kb"
                  />
                  <span className="truncate">{p.name}</span>
                </label>
              </li>
            ))}
          </ul>
        </section>

        {error && <p className="text-[12px] text-error">{error}</p>}
      </div>

      <div className="p-5 border-t border-border-soft flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-sm font-medium border border-border-soft rounded-md hover:bg-surface"
        >
          {t("modal.cancel")}
        </button>
        <button
          type="button"
          onClick={handleExport}
          disabled={busy || count === 0}
          className="px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {t("export.confirmButton", { count })}
        </button>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/ExportImportDialog.tsx
git commit -m "feat(admin): implement Export tab with provider checkboxes"
```

---

### Task 6: Implement Import tab (drop-zone + inline preview)

This tab subsumes the entire existing `ImportPreviewDialog.tsx`. We replicate its rendering inline (rather than reusing it as a child) because the spec says the file is removed afterward.

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/ExportImportDialog.tsx` — replace the placeholder `ImportTab` function and add helpers.

- [ ] **Step 1: Extend imports**

At the top of the file:

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
```

Update the icons import to include `CheckCircle`:

```tsx
import { CheckCircle, Warning } from "@phosphor-icons/react";
```

- [ ] **Step 2: Replace `ImportTab` and add helpers**

Replace the placeholder `function ImportTab(...)` with the following block. Note: the per-provider hint texts and badges are intentionally identical strings to those used today in `ImportPreviewDialog.tsx` (see [`ImportPreviewDialog.tsx:74-96`](../../../frontend/src/app/[locale]/admin/_components/providers/ImportPreviewDialog.tsx#L74-L96)).

```tsx
function ImportTab({
  onCancel,
  onPreview,
  onConfirm,
  setSubmitting,
}: {
  onCancel: () => void;
  onPreview: (config: unknown) => Promise<ImportPreviewResult>;
  onConfirm: (config: unknown) => Promise<void>;
  setSubmitting: (v: boolean) => void;
}) {
  const t = useTranslations("admin.providers.exportImport");
  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "loading"; filename: string }
    | { kind: "previewed"; filename: string; config: unknown; preview: ImportPreviewResult }
    | { kind: "error"; message: string }
  >({ kind: "idle" });
  const [confirming, setConfirming] = useState(false);

  const handleFile = async (file: File) => {
    setState({ kind: "loading", filename: file.name });
    try {
      const text = await file.text();
      let config: unknown;
      try {
        config = JSON.parse(text);
      } catch {
        setState({ kind: "error", message: t("errors.invalidJson") });
        return;
      }
      const preview = await onPreview(config);
      setState({ kind: "previewed", filename: file.name, config, preview });
    } catch (err) {
      setState({
        kind: "error",
        message: t("errors.importFailed", { message: (err as Error).message }),
      });
    }
  };

  const handleConfirm = async () => {
    if (state.kind !== "previewed") return;
    setConfirming(true);
    setSubmitting(true);
    try {
      await onConfirm(state.config);
    } catch (err) {
      setState({
        kind: "error",
        message: t("errors.importFailed", { message: (err as Error).message }),
      });
    } finally {
      setConfirming(false);
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="p-5 space-y-5">
        {(state.kind === "idle" || state.kind === "error") && (
          <DropZone onFile={handleFile} />
        )}
        {state.kind === "loading" && (
          <p className="text-sm text-muted">{state.filename}…</p>
        )}
        {state.kind === "error" && (
          <p className="text-[12px] text-error">{state.message}</p>
        )}
        {state.kind === "previewed" && (
          <>
            <div className="text-xs text-muted flex items-center gap-2">
              <span className="truncate">{state.filename}</span>
              <button
                type="button"
                onClick={() => setState({ kind: "idle" })}
                className="text-kb hover:underline"
              >
                ({t("import.chooseAnotherFile")})
              </button>
            </div>
            <PreviewBody preview={state.preview} />
          </>
        )}
      </div>

      <div className="p-5 border-t border-border-soft flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={confirming}
          className="px-3 py-1.5 text-sm font-medium border border-border-soft rounded-md hover:bg-surface disabled:opacity-50"
        >
          {t("modal.cancel")}
        </button>
        {state.kind === "previewed" && (
          <button
            type="button"
            onClick={handleConfirm}
            disabled={confirming}
            className="px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb disabled:opacity-50"
          >
            {t("import.confirmButton")}
          </button>
        )}
      </div>
    </>
  );
}

function DropZone({ onFile }: { onFile: (file: File) => void }) {
  const t = useTranslations("admin.providers.exportImport.import");
  const [hover, setHover] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault();
        setHover(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
        hover ? "border-kb bg-surface" : "border-border-soft hover:bg-surface"
      }`}
    >
      <p className="text-sm text-muted">{t("dropzoneHint")}</p>
      <input
        ref={inputRef}
        type="file"
        accept="application/json"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}

function PreviewBody({ preview }: { preview: ImportPreviewResult }) {
  const t = useTranslations("admin.providers.exportImport.preview");
  return (
    <>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
          {t("providersHeading", { count: preview.providers.length })}
        </h3>
        <ul className="space-y-3">
          {preview.providers.map((p) => (
            <li key={p.name}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-foreground truncate">{p.name}</span>
                <PreviewBadge action={p.action} />
              </div>
              {p.protocol_change && (
                <p className="mt-1 text-[12px] text-amber-700 dark:text-amber-400 border-l-2 border-amber-500 pl-2">
                  {t("protocolChange", p.protocol_change)}
                </p>
              )}
              {p.needs_api_key && !p.existing_has_key && (
                <p className="mt-1 text-[12px] text-red-600 dark:text-red-400 border-l-2 border-red-600 pl-2 flex items-center gap-1">
                  <Warning size={12} weight="bold" />
                  {t("apiKeyMissing")}
                </p>
              )}
              {p.needs_api_key && p.existing_has_key && (
                <p className="mt-1 text-[12px] text-green-700 dark:text-green-400 border-l-2 border-green-600 pl-2 flex items-center gap-1">
                  <CheckCircle size={12} weight="bold" />
                  {t("apiKeyPreserved")}
                </p>
              )}
              {!p.needs_api_key && (
                <p className="mt-1 text-[12px] text-green-700 dark:text-green-400 border-l-2 border-green-600 pl-2 flex items-center gap-1">
                  <CheckCircle size={12} weight="bold" />
                  {t("apiKeyNotNeeded")}
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
          {t("routesHeading", { count: preview.routes.length })}
        </h3>
        <ul className="space-y-1.5">
          {preview.routes.map((r, i) => (
            <li key={`${r.feature}-${i}`} className="text-sm flex items-start gap-2">
              {r.action === "skip_unresolved" ? (
                <>
                  <Warning size={14} weight="bold" className="text-amber-600 mt-0.5" />
                  <span className="text-foreground">
                    <span className="font-medium">{r.feature}</span> —{" "}
                    <span className="text-amber-700 dark:text-amber-400">
                      {t("routeSkipped", { provider: extractProviderFromReason(r.reason) })}
                    </span>
                  </span>
                </>
              ) : (
                <>
                  <CheckCircle size={14} weight="bold" className="text-green-600 mt-0.5" />
                  <span className="text-foreground">
                    <span className="font-medium">{r.feature}</span> → {r.resolved_provider}
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function PreviewBadge({ action }: { action: "create" | "update" }) {
  const t = useTranslations("admin.providers.exportImport.preview.badge");
  const classes = action === "create"
    ? "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300"
    : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${classes}`}>
      {t(action === "create" ? "new" : "merge")}
    </span>
  );
}

function extractProviderFromReason(reason: string): string {
  const m = /['"„]([^'"]+)['"]/.exec(reason);
  return m ? m[1] : reason;
}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/ExportImportDialog.tsx
git commit -m "feat(admin): implement Import tab with drop-zone and inline preview"
```

---

### Task 7: Wire the dialog into `providers/index.tsx`

Replace the old DialogState variant, handlers, and JSX. The legacy `ImportPreviewDialog` import and render are removed; `exportConfig` (Blob variant) and `importPreview` are no longer called from this file.

**Files:**
- Modify: [`frontend/src/app/[locale]/admin/_components/providers/index.tsx`](../../../frontend/src/app/[locale]/admin/_components/providers/index.tsx)

- [ ] **Step 1: Update imports**

Change the API-import block (currently lines 7–21):

```tsx
import {
  clearAllProviders,
  createProvider,
  deleteProvider,
  fetchAffectedFeatures,
  fetchMeta,
  fetchProviders,
  fetchRoutes,
  importConfig,
  importPreview,
  probeProvider,
  setFeatureRoute,
  updateProvider,
} from "./_api";
```

(removed `exportConfig` from the list; `importPreview` stays because index passes it as a callback)

Change the component imports (currently around line 25):

```tsx
import ProviderListCard from "./ProviderListCard";
import ProviderFormDialog from "./ProviderFormDialog";
import FeatureRoutingCard from "./FeatureRoutingCard";
import ExportImportDialog from "./ExportImportDialog";
import ClearAllConfirmDialog from "./ClearAllConfirmDialog";
```

(removed `ImportPreviewDialog` import)

- [ ] **Step 2: Replace `DialogState`**

Replace the existing `DialogState` (lines 28–38) with:

```tsx
type DialogState =
  | { open: false }
  | { open: true; mode: "create" }
  | { open: true; mode: "edit"; provider: Provider }
  | { open: true; mode: "export-import"; initialTab: "export" | "import" };
```

- [ ] **Step 3: Replace `handleExport`, `handleImportFile`, `handleImportConfirm`**

Find the current `handleExport` (around lines 207–222), `handleImportFile` (~224–245), `handleImportConfirm` (~247–257). Replace them with:

```tsx
const handleExportDownload = useCallback((config: unknown, filename: string) => {
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  setDialog({ open: false });
}, []);

const handleImportConfirm = useCallback(async (config: unknown) => {
  await importConfig(config);
  setDialog({ open: false });
  await refreshAll();
}, [refreshAll]);

const handleOpenExportImport = useCallback((initialTab: "export" | "import") => {
  setDialog({ open: true, mode: "export-import", initialTab });
}, []);
```

(No more `window.alert` on import success — the modal close plus refreshed list is the feedback.)

- [ ] **Step 4: Update `<ProviderListCard>` props**

Find the existing usage (around lines 282–291). Replace:

```tsx
<ProviderListCard
  providers={providers}
  onAdd={() => setDialog({ open: true, mode: "create" })}
  onEdit={(p) => setDialog({ open: true, mode: "edit", provider: p })}
  onProbe={handleProbe}
  onDelete={handleDelete}
  onOpenExportImport={handleOpenExportImport}
  onClearAll={handleClearAllRequest}
/>
```

- [ ] **Step 5: Replace the dialog JSX**

Find the existing `{dialog.open && dialog.mode === "import-preview" && (…<ImportPreviewDialog/>…)}` block (around lines 315–324). Replace it with:

```tsx
{dialog.open && dialog.mode === "export-import" && (
  <ExportImportDialog
    providers={providers}
    initialTab={dialog.initialTab}
    onClose={() => setDialog({ open: false })}
    onExportDownload={handleExportDownload}
    onImportPreview={importPreview}
    onImportConfirm={handleImportConfirm}
  />
)}
```

Leave the `ProviderFormDialog` and `ClearAllConfirmDialog` JSX blocks unchanged.

- [ ] **Step 6: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean. If you get an error about `onExport`/`onImport` missing from `ProviderListCard` props, that's expected — Task 8 fixes the consumer.

- [ ] **Step 7: Commit**

Even with a transient TS error, this commit is meaningful — Task 8 lands the matching consumer update right after. If TS is red, you can fold Task 8 into the same commit.

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/index.tsx
git commit -m "refactor(admin): replace ImportPreviewDialog wiring with ExportImportDialog"
```

---

### Task 8: Update `ProviderListCard` — remove top-level buttons, add kebab item

**Files:**
- Modify: [`frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx`](../../../frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx)

- [ ] **Step 1: Update imports**

Remove these phosphor icons that are no longer used in the toolbar: `DownloadSimple`, `UploadSimple`. Keep `Cube`, `DotsThreeVertical`, `ArrowsClockwise`, `NotePencil`, `Plus`, `Trash`. Drop the `HelpTooltip` import added earlier.

After edits, the top of the file should be:

```tsx
"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowsClockwise, Cube, DotsThreeVertical, NotePencil, Plus, Trash, UploadSimple } from "@phosphor-icons/react";
import type { Provider } from "./_types";
```

(`UploadSimple` stays — `EmptyState` still uses it. `DownloadSimple` and `HelpTooltip` are removed.)

- [ ] **Step 2: Update `Props` type**

Replace the existing `Props` (lines 15–24) with:

```tsx
type Props = {
  providers: Provider[];
  onAdd: () => void;
  onEdit: (p: Provider) => void;
  onProbe: (p: Provider) => Promise<void> | void;
  onDelete: (p: Provider) => void;
  onOpenExportImport: (initialTab: "export" | "import") => void;
  onClearAll: () => void;
};
```

Update the destructuring in the default export to match (replace lines 26–35):

```tsx
export default function ProviderListCard({
  providers,
  onAdd,
  onEdit,
  onProbe,
  onDelete,
  onOpenExportImport,
  onClearAll,
}: Props) {
  const t = useTranslations("admin.providers");
  const [menuOpen, setMenuOpen] = useState(false);
```

Drop the `const fileInputRef = useRef<HTMLInputElement>(null);` line — only `EmptyState` needs its own ref now.

- [ ] **Step 3: Remove the top-level Export and Import buttons + hidden input**

In the toolbar block (current lines 52–120, the `{providers.length > 0 && (…)}` div), delete:
- The `<span>` wrapping the Export button and `<HelpTooltip>` (added in the previous session)
- The hidden `<input ref={fileInputRef} type="file" …>`
- The Import `<button>` that triggers `fileInputRef.current?.click()`

Keep:
- The `+ Hinzufügen` button (`onAdd`)
- The kebab `<div className="relative">…</div>` (modified next step)

After this edit, the toolbar's right side should contain only the Add button followed by the kebab.

- [ ] **Step 4: Add the kebab menu item**

In the kebab dropdown (currently shows only the `Alle löschen` button), prepend a new Export/Import item plus a divider. The kebab `<div className="absolute …py-1">` block becomes:

```tsx
<div className="absolute right-0 top-full mt-1 w-56 bg-background border border-border-soft rounded-md shadow-lg z-50 py-1">
  <button
    type="button"
    onClick={() => {
      setMenuOpen(false);
      onOpenExportImport("export");
    }}
    className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-surface"
  >
    {t("list.exportImportMenuItem")}
  </button>
  <div className="my-1 border-t border-border-soft" />
  <button
    type="button"
    onClick={() => {
      setMenuOpen(false);
      onClearAll();
    }}
    className="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30"
  >
    {t("clearAll.menuItem")}
  </button>
</div>
```

(menu width bumped from `w-48` to `w-56` to fit the longer label comfortably).

- [ ] **Step 5: Update `EmptyState` to open the modal in Import tab**

Replace the `EmptyState` function (lines 142–181). Drop the `onImport: (file: File) => void` prop and replace with `onOpenExportImport: (initialTab: "export" | "import") => void`. Remove the hidden file input and its handler — the dropzone now lives in the modal.

```tsx
function EmptyState({
  onAdd,
  onOpenExportImport,
}: {
  onAdd: () => void;
  onOpenExportImport: (initialTab: "export" | "import") => void;
}) {
  const t = useTranslations("admin.providers");
  return (
    <div className="text-center py-10 px-6 border border-dashed border-border-soft rounded-lg">
      <Cube size={32} weight="bold" className="mx-auto text-muted mb-3" />
      <p className="text-sm font-medium text-foreground mb-1">{t("list.emptyTitle")}</p>
      <p className="text-xs text-muted-soft mb-4 max-w-md mx-auto">{t("list.emptyHint")}</p>
      <div className="flex items-center justify-center gap-2">
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb transition-colors"
        >
          <Plus size={14} weight="bold" />
          {t("list.add")}
        </button>
        <button
          type="button"
          onClick={() => onOpenExportImport("import")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-foreground border border-border-soft bg-background rounded-md hover:bg-surface transition-colors"
        >
          <UploadSimple size={14} weight="bold" />
          {t("exportImport.importButton")}
        </button>
      </div>
    </div>
  );
}
```

Update the `EmptyState` call site (currently `<EmptyState onAdd={onAdd} onImport={onImport} />` around line 124):

```tsx
<EmptyState onAdd={onAdd} onOpenExportImport={onOpenExportImport} />
```

- [ ] **Step 6: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean. The error from Task 7 should now be resolved.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/ProviderListCard.tsx
git commit -m "refactor(admin): replace toolbar export/import with kebab menu entry"
```

---

### Task 9: Remove `ImportPreviewDialog.tsx` and `exportConfig` Blob helper

**Files:**
- Delete: `frontend/src/app/[locale]/admin/_components/providers/ImportPreviewDialog.tsx`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/_api.ts` — remove the now-unused `exportConfig` function.

- [ ] **Step 1: Confirm nothing else references them**

```bash
grep -rn "ImportPreviewDialog\|exportConfig\b" frontend/src/ 2>/dev/null
```
Expected: only matches inside `_api.ts` itself (the function definition) and the file you're about to delete. If anything else shows up, stop and revisit Task 7.

- [ ] **Step 2: Delete the file**

```bash
git rm frontend/src/app/\[locale\]/admin/_components/providers/ImportPreviewDialog.tsx
```

- [ ] **Step 3: Remove `exportConfig` from `_api.ts`**

Delete the function block at [`_api.ts:167-177`](../../../frontend/src/app/[locale]/admin/_components/providers/_api.ts#L167-L177):

```typescript
export async function exportConfig(): Promise<{ blob: Blob; filename: string }> {
  …
}
```

Leave `fetchExportConfig`, `importPreview`, `importConfig`, and `clearAllProviders` in place.

- [ ] **Step 4: Verify TypeScript and grep again**

```bash
cd frontend && npx tsc --noEmit
grep -rn "ImportPreviewDialog\|exportConfig\b" frontend/src/
```
Expected: TS clean. Grep returns nothing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/_api.ts
git commit -m "chore(admin): drop obsolete ImportPreviewDialog and exportConfig blob helper"
```

---

### Task 10: Drop unused `importSuccessToast` i18n string

Now that the modal close + refresh is the feedback for a successful import, the string is dead.

**Files:**
- Modify: `frontend/messages/de.json`
- Modify: `frontend/messages/en.json`

- [ ] **Step 1: Remove the `importSuccessToast` key from both locale files**

In each file, inside `admin.providers.exportImport`, delete the line:

```json
"importSuccessToast": "...",
```

- [ ] **Step 2: Verify nothing references it**

```bash
grep -rn "importSuccessToast" frontend/src/ frontend/messages/ 2>/dev/null
```
Expected: no matches.

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/messages/de.json frontend/messages/en.json
git commit -m "i18n(admin): drop unused importSuccessToast"
```

---

### Task 11: Manual verification in the browser

No automated UI tests exist for this admin tab — drive the feature by hand and observe.

- [ ] **Step 1: Start the dev server**

Follow whatever the project's normal start commands are (consult repo `CLAUDE.md` or the `/run` skill). Typical for Next.js: `cd frontend && npm run dev`.

- [ ] **Step 2: Walk the Export path**

In a browser:
1. Sign in as admin, navigate to Admin → AI / Provider tab.
2. Confirm top-level Export and Import buttons are gone; only `+ Hinzufügen` and the kebab remain.
3. Click the kebab. Confirm the menu shows: `Export / Import…`, divider, `Alle löschen`.
4. Click `Export / Import…`. Confirm the modal opens on the Export tab.
5. Confirm the amber API-key hint is visible.
6. Confirm all providers are pre-selected with checkboxes and the counter reads `n von n`.
7. Click `Keine` — all checkboxes clear, counter becomes `0 von n`, Export button is disabled.
8. Click `Alle` — selection restored.
9. Uncheck one provider; click `Exportieren (n−1)`. A JSON file downloads.
10. Open the downloaded JSON. Confirm the unchecked provider is missing from `providers[]`, and any `feature_routes` that pointed at it are gone. Routes that referenced the provider in `user_choices` or `provider_models` should have those entries pruned but the route itself preserved.

- [ ] **Step 3: Walk the Import path**

1. Reopen the modal, switch to the `Importieren` tab.
2. Confirm the drop-zone is visible with the hint text.
3. Drop the JSON from Step 2 onto the drop-zone. Confirm the preview renders with Provider list, NEW/MERGE badges, API-key per-provider hints, and Feature-Routes section.
4. Click `Andere Datei wählen`. Confirm the drop-zone is shown again.
5. Pick the file via Click → file picker. Same preview should appear.
6. Click `Import bestätigen`. Modal closes, provider list refreshes.

- [ ] **Step 4: Walk the Empty-State path**

1. Open the kebab menu, click `Alle löschen`, confirm the clear-all dialog appears, confirm.
2. With 0 providers, confirm the `EmptyState` renders an `+ Hinzufügen` and `Importieren` button.
3. Click `Importieren`. Modal opens directly on the Import tab.

- [ ] **Step 5: Walk the Esc / click-outside behaviour**

1. Reopen the modal. Hit `Esc` — modal closes.
2. Reopen, click on the dark backdrop — modal closes.
3. Reopen, click inside the modal body — modal stays open.

- [ ] **Step 6: Verify file structure on disk**

```bash
ls frontend/src/app/\[locale\]/admin/_components/providers/
```
Expected files:
```
ClearAllConfirmDialog.tsx
ExportImportDialog.tsx
FeatureRoutingCard.tsx
ProviderFormDialog.tsx
ProviderListCard.tsx
VoicesEditor.tsx
_api.ts
_exportFilter.ts
_types.ts
index.tsx
```
(`ImportPreviewDialog.tsx` should be gone.)

- [ ] **Step 7: Final commit (if any tweaks needed)**

If verification surfaced cosmetic issues, fix them with targeted commits. If everything works, no commit is needed.

---

## Out-of-scope reminder

Per the spec's "Offen" section, the following are explicitly NOT part of this plan:
- Backend `?provider_ids=…` filter parameter
- Toast/banner success feedback after import
- Frontend test harness setup
