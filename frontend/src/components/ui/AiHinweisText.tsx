"use client";

import { useTranslations } from "next-intl";

interface AiHinweisTextProps {
  className?: string;
}

/** A quiet one-line notice next to a download button, for files with AI-generated content. */
export default function AiHinweisText({ className = "" }: AiHinweisTextProps) {
  const t = useTranslations("common");
  return <p className={`text-xs text-muted-soft ${className}`}>{t("aiHinweis")}</p>;
}
