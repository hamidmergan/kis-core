"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Warning, CheckCircle } from "@phosphor-icons/react";
import type { ImportPreviewResult } from "./_types";

type Props = {
  filename: string;
  exportedAt?: string;
  exportedFrom?: string;
  preview: ImportPreviewResult;
  onCancel: () => void;
  onConfirm: () => Promise<void> | void;
};

export default function ImportPreviewDialog({
  filename, exportedAt, exportedFrom, preview, onCancel, onConfirm,
}: Props) {
  const t = useTranslations("admin.providers.exportImport.preview");
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border border-border-soft rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto">
        <div className="p-5 border-b border-border-soft">
          <h2 className="text-base font-semibold text-foreground">{t("title")}</h2>
          <p className="text-xs text-muted mt-1">{t("source", { filename })}</p>
          {exportedAt && (
            <p className="text-xs text-muted">
              {t("createdAt", {
                date: exportedAt.slice(0, 10),
                from: exportedFrom ?? "none",
              })}
            </p>
          )}
        </div>

        <div className="p-5 space-y-5">
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
              {t("providersHeading", { count: preview.providers.length })}
            </h3>
            <ul className="space-y-3">
              {preview.providers.map((p) => (
                <li key={p.name}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground truncate">
                      {p.name}
                    </span>
                    <Badge action={p.action} />
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
                        <span className="font-medium">{r.feature}</span> →{" "}
                        {r.resolved_provider}
                      </span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="p-5 border-t border-border-soft flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            autoFocus
            className="px-3 py-1.5 text-sm font-medium border border-border-soft rounded-md hover:bg-surface"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting}
            className="px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb disabled:opacity-50"
          >
            {t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

function Badge({ action }: { action: "create" | "update" }) {
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

/** Extracts the quoted provider name out of the backend's
 *  "Provider 'X' nicht im Import enthalten" message so the UI message
 *  can use its own translated wrapper. Falls back to the whole reason. */
function extractProviderFromReason(reason: string): string {
  const m = /['"„]([^'"]+)['"]/.exec(reason);
  return m ? m[1] : reason;
}
