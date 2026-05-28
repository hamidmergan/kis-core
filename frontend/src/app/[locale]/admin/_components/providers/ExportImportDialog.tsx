"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { CheckCircle } from "@phosphor-icons/react";
import { filterExportConfig } from "./_exportFilter";
import { fetchExportConfig } from "./_api";
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
        <p className="text-[12px] text-amber-700 dark:text-amber-400">
          {t("exportHint")}
        </p>

        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
              {t("export.providersHeading")}
            </h3>
            <span className="text-xs text-muted">
              {t("export.selectedCount", { selected: count, total })}
            </span>
          </div>
          <ul className="space-y-1.5">
            <li>
              <label className="flex items-center gap-2 text-sm font-medium text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = count > 0 && count < total;
                  }}
                  onChange={toggleAll}
                  className="accent-kb"
                />
                <span>{t("export.selectAll")}</span>
              </label>
            </li>
            <li aria-hidden="true">
              <div className="border-t border-border-soft my-1" />
            </li>
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
                <p className="mt-1 text-[12px] text-red-600 dark:text-red-400 border-l-2 border-red-600 pl-2">
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
