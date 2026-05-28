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
