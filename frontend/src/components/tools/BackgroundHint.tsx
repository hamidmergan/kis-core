"use client";

import { useTranslations } from "next-intl";
import { Info } from "@phosphor-icons/react";

/** One uniform line for every tool: a running job survives leaving the page. */
export default function BackgroundHint({ className = "mt-6" }: { className?: string }) {
  const t = useTranslations("common");
  return (
    <p className={`flex items-start gap-2 rounded-lg bg-surface px-4 py-3 text-left text-sm text-foreground-soft ${className}`}>
      <Info size={14} className="mt-0.5 flex-shrink-0 text-muted-soft" aria-hidden="true" />
      {t("jobBackgroundHint")}
    </p>
  );
}
