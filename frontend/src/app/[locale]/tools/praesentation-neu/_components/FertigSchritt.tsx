"use client";

import { DownloadSimple } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import BackgroundHint from "@/components/tools/BackgroundHint";
import Spinner from "@/components/ui/Spinner";
import FolienGrossbild from "../../praesentation/_components/FolienGrossbild";
import { downloadUrl, previewUrl } from "../../praesentation/_api";
import { LAEUFT, fortschrittMeldung } from "../../praesentation/_logic";
import type { JobProgress, JobStatus, Slide } from "../../praesentation/_types";

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
}

const cancelIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const NEBENKNOPF = "w-full sm:w-auto px-6 py-2.5 sm:py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors";

/** The finished deck as a strip of slides, a click shows one large, the download pinned on the phone. */
export default function FertigSchritt(p: DoneStepProps) {
  const [gross, setGross] = useState<number | null>(null);
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
        <BackgroundHint />
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
      <h2 className="text-lg font-bold text-center">{t("heading")}</h2>
      <p className="text-sm text-muted mt-1 mb-6 text-center">{t("summary", { n: p.slides.length })}</p>

      <ol className="flex gap-2.5 sm:gap-4 overflow-x-auto scrollbar-hide pb-1.5 sm:flex-wrap sm:justify-center" aria-label={t("allSlides")}>
        {p.slides.map((s, i) => {
          const url = typeof p.previews[s.id] === "number" ? previewUrl(p.jobUuid, s.id, p.previews[s.id]) : null;
          return (
            <li key={s.id} className="shrink-0">
              <button type="button" onClick={() => setGross(i)} aria-label={tSlides("openPreview", { n: i + 1 })}
                      className="block w-32 sm:w-40 rounded-md overflow-hidden border-2 border-border-soft hover:border-kb shadow-sm transition-colors cursor-zoom-in">
                {url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={url} alt="" loading="lazy" className="block w-full aspect-video object-cover" />
                ) : (
                  <span className="block aspect-video bg-surface" />
                )}
              </button>
            </li>
          );
        })}
      </ol>

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

      {gross !== null && (
        <FolienGrossbild index={gross} total={p.slides.length}
          previewUrl={typeof p.previews[p.slides[gross]?.id] === "number" ? previewUrl(p.jobUuid, p.slides[gross].id, p.previews[p.slides[gross].id]) : null}
          onClose={() => setGross(null)} onIndexChange={setGross} />
      )}
    </section>
  );
}
