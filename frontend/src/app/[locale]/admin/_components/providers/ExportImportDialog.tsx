"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Warning } from "@phosphor-icons/react";
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

function ImportTab(_: {
  onCancel: () => void;
  onPreview: (config: unknown) => Promise<ImportPreviewResult>;
  onConfirm: (config: unknown) => Promise<void>;
  setSubmitting: (v: boolean) => void;
}) {
  return <div className="p-5 text-sm text-muted">Import tab — implemented in Task 6</div>;
}
