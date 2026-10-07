"use client";

import { useTranslations } from "next-intl";
import { Info } from "@phosphor-icons/react";

/** One uniform line for every tool, always the first thing of a running view: a running job survives leaving the page. */
export default function BackgroundHint() {
  const t = useTranslations("common");
  return (
    <p className="mb-6 flex w-full items-start gap-2 rounded-lg border border-border bg-background px-4 py-3 text-left text-sm text-foreground-soft">
      <Info size={14} className="mt-0.5 flex-shrink-0 text-kb-dark" aria-hidden="true" />
      {t("jobBackgroundHint")}
    </p>
  );
}
