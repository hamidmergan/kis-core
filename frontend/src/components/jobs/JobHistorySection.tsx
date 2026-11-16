"use client";

import { useLocale, useTranslations } from "next-intl";
import type { JobHistoryEntry } from "@/hooks/useJobHistory";
import JobHistoryTable from "./JobHistoryTable";

/** Heading, hint and table of the last runs below a tool page. */
export default function JobHistorySection({ namespace, entries, selectedUuid, disabled, onSelect }: {
  namespace: "tools.translate.history" | "tools.stt.history" | "tools.tts.history" | "tools.summarize.history";
  entries: JobHistoryEntry[];
  selectedUuid: string | null;
  disabled?: boolean;
  onSelect: (jobUuid: string) => void;
}) {
  const t = useTranslations(namespace);
  const locale = useLocale();
  return (
    <div className="mt-10">
      <h2 className="text-sm font-semibold text-foreground mb-1">{t("title")}</h2>
      <p className="text-xs text-muted mb-3">{entries.length ? t("hint") : t("empty")}</p>
      {entries.length > 0 && (
        <JobHistoryTable
          entries={entries}
          selectedUuid={selectedUuid}
          disabled={disabled}
          locale={locale}
          colMaterial={t("colMaterial")}
          colDate={t("colDate")}
          onSelect={onSelect}
        />
      )}
    </div>
  );
}
