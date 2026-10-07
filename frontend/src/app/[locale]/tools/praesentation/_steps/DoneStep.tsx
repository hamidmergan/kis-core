"use client";

import { DownloadSimple } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import BackgroundHint from "@/components/tools/BackgroundHint";
import Spinner from "@/components/ui/Spinner";
import type { Auftrag } from "@/components/jobs/ErgebnisInfo";
import FolienBetrachter from "../_components/FolienBetrachter";
import PraesentationInfo from "../_components/PraesentationInfo";
import { downloadUrl, previewUrl } from "../_api";
import { LAEUFT, fortschrittMeldung } from "../_logic";
import type { JobProgress, JobStatus, Slide } from "../_types";

interface DoneStepProps {
  jobUuid: string;
  slides: Slide[];
  previews: Record<string, number>;
  jobStatus: JobStatus;
  progress: JobProgress | null;
  error: string;
  onResume: () => void;
  onBackToPreview: () => void;
  onNew: () => void;
  onCancel: () => void;
  /** The prepared demo run, nothing runs in the background there. */
  demo?: boolean;
  /** The demo brings its info along, a real run reads it from its job. */
  auftrag?: Auftrag;
}

const cancelIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const NEBENKNOPF = "w-full sm:w-auto px-6 py-2.5 sm:py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors";

/** The finished deck to page through, one slide large over the strip of all, the download pinned on the phone. */
export default function DoneStep(p: DoneStepProps) {
  const t = useTranslations("tools.praesentation.done");
  const tSlides = useTranslations("tools.praesentation.slides");
  const tCommon = useTranslations("tools.praesentation.common");

  if (LAEUFT.has(p.jobStatus)) {
    const meldung = fortschrittMeldung(p.jobStatus, p.progress);
    return (
      <section className="animate-[fadeIn_0.3s_ease-out] text-center py-10" aria-live="polite">
        <Spinner size="lg" className="justify-center mb-4" />
        <h2 className="text-lg font-bold">{t("building")}</h2>
        <p className="text-sm text-foreground-soft mt-1">{tSlides(meldung.key, meldung.values)}</p>
        {!p.demo && <BackgroundHint />}
        <button type="button" onClick={p.onCancel}
                className="btn-cancel mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2">
          {cancelIcon}
          {tCommon("cancel")}
        </button>
      </section>
    );
  }

  if (p.jobStatus !== "success") {
    const gestoert = p.jobStatus === "failed" || p.jobStatus === "paused";
    return (
      <section className="animate-[fadeIn_0.3s_ease-out] py-4">
        {gestoert && (
          <div className="rounded-xl border-2 border-error-border p-3">
            <p className="text-sm text-error">{p.error || tSlides("failed")}</p>
            <button type="button" className="mt-2 px-4 py-2 text-sm btn-primary rounded-lg" onClick={p.onResume}>
              {tSlides("retry")}
            </button>
          </div>
        )}
        <div className="flex justify-center mt-6">
          <button type="button" onClick={p.onBackToPreview} className={NEBENKNOPF}>{t("backToSlides")}</button>
        </div>
      </section>
    );
  }

  // The link deliberately does not sit in the page, otherwise the top loader runs forever.
  const herunterladen = () => {
    const a = document.createElement("a");
    a.href = downloadUrl(p.jobUuid);
    a.download = "";
    a.click();
  };

  return (
    <section className="animate-[fadeIn_0.3s_ease-out] py-4">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: "var(--kb)" }}>
          <svg className="w-6 h-6" style={{ color: "#fff" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </div>
      <div className="flex items-center justify-center gap-1">
        <h2 className="text-lg font-bold text-center">{t("heading")}</h2>
        <PraesentationInfo jobUuid={p.jobUuid} bereit={p.jobStatus === "success"} auftrag={p.auftrag} />
      </div>
      <p className="text-sm text-muted mt-1 mb-6 text-center">{t("summary", { n: p.slides.length })}</p>

      <FolienBetrachter ids={p.slides.map((s) => s.id)}
        urlFuer={(id) => (typeof p.previews[id] === "number" ? previewUrl(p.jobUuid, id, p.previews[id]) : null)} />

      {/* Desktop: download above the two side buttons. Phone: side buttons first, download pinned below. */}
      <div className="flex flex-col">
      <div className="order-last sm:order-none sticky bottom-0 z-30 -mx-4 px-4 py-3 mt-6 border-t border-border-soft bg-background sm:static sm:mx-0 sm:px-0 sm:py-0 sm:border-0 sm:bg-transparent sm:mt-9 sm:mb-6 sm:flex sm:justify-center">
        <button
          type="button"
          onClick={herunterladen}
          className="w-full sm:w-auto px-6 py-3 sm:py-2 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center justify-center gap-2"
        >
          <DownloadSimple size={16} weight="bold" />
          {t("download")}
        </button>
      </div>

      <div className="flex flex-col sm:flex-row sm:flex-wrap sm:justify-center gap-2 sm:gap-3 mt-6 sm:mt-0">
        <button type="button" onClick={p.onBackToPreview} className={NEBENKNOPF}>{t("backToSlides")}</button>
        <button type="button" onClick={p.onNew} className={NEBENKNOPF}>{t("new")}</button>
      </div>
      </div>

    </section>
  );
}
