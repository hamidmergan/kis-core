"use client";

import { useTranslations } from "next-intl";
import { downloadUrl } from "../_api";

interface DoneStepProps {
  jobUuid: string;
  slides: number;
  onBackToSlides: () => void;
  onNew: () => void;
}

export default function DoneStep({ jobUuid, slides, onBackToSlides, onNew }: DoneStepProps) {
  const t = useTranslations("tools.praesentation.done");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-4">
      <h2 className="text-lg font-bold">{t("heading")}</h2>
      <p className="text-sm text-muted mt-1">{t("summary", { n: slides })}</p>
      <a href={downloadUrl(jobUuid)} className="inline-block px-4 py-2 btn-primary text-sm font-medium rounded-md  transition-colors mb-6">{t("download")}</a>
      <p className="text-xs text-muted">{t("expiryHint")}</p>
      <div className="flex gap-3 mt-10 justify-center">
        <button type="button" onClick={onBackToSlides} className="px-4 py-3 text-sm text-foreground-soft border-2 border-border rounded-md hover:border-kb transition-colors">{t("backToSlides")}</button>
        <button type="button" onClick={onNew} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">{t("new")}</button>
      </div>
    </section>
  );
}
