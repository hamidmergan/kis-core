"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type { SlideData } from "@/types";
import StatusMark from "@/components/ui/StatusMark";
import StepFooter from "./StepFooter";

interface TranslationReviewStepProps {
  onBack: (() => void) | null;
  slides: SlideData[];
  loading: boolean;
  correctedFileName: string | null;
  uploadFehler: string;
  skipTranslation: boolean;
  onLightboxOpen: (index: number) => void;
  onDownloadTranslatedPptx: () => Promise<boolean>;
  onUploadCorrectedPptx: (f: File) => void;
  onAcceptAndNext: () => void;
  /** The demo offers no upload of an own file. */
  demo?: boolean;
}

export default function TranslationReviewStep({
  onBack,
  slides,
  loading,
  correctedFileName,
  uploadFehler,
  skipTranslation,
  onLightboxOpen,
  onDownloadTranslatedPptx,
  onUploadCorrectedPptx,
  onAcceptAndNext,
  demo = false,
}: TranslationReviewStepProps) {
  const t = useTranslations("tools.screencast");
  const tDemo = useTranslations("tools.screencastDemo");
  const [downloadFailed, setDownloadFailed] = useState(false);
  const unchangedCount = slides.filter((s) => s.unchanged).length;
  // The same endpoint also reports an empty file and too many slides, the heading only fits the slide count message.
  const istFolienzahlFehler = /folien(nummer|zahl)|slide (number|count)/i.test(uploadFehler);
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-2">
        {t(skipTranslation ? "translationReview.headingOhneUebersetzung" : "translationReview.heading")}
      </h2>
      <p className="text-sm text-muted mb-6">
        {t(skipTranslation ? "translationReview.introOhneUebersetzung" : "translationReview.intro")}
      </p>

      {unchangedCount > 0 && (
        <div className="mb-4 rounded-md border border-warn-border bg-warn-bg px-3 py-2">
          <p className="text-sm font-medium text-warn-strong">
            {t("translationReview.unchangedTitle", { n: unchangedCount })}
          </p>
          <p className="mt-0.5 text-sm text-warn">{t("translationReview.unchangedBody")}</p>
        </div>
      )}

      {/* Nur die Folienbilder. Der erkannte Folientext stand hier eine Zeit lang
          daneben, das war überflüssig: seit Extraktion und Übersetzung dieselbe
          Stelle im Code nutzen, sagt schon das Bild, ob der Text gefunden wurde.
          Was bleibt, ist die Markierung nicht übersetzter Folien. */}
      <div className="flex flex-wrap justify-center gap-2 mb-6">
        {slides.map((slide, i) => (
          <button
            key={i}
            onClick={() => onLightboxOpen(i)}
            style={{ width: "100px" }}
            className={`relative rounded-lg overflow-hidden border transition-colors focus-visible:outline-2 focus-visible:outline-kb group flex-shrink-0 ${
              slide.unchanged ? "border-warn-border" : "border-border-soft hover:border-kb"
            }`}
            aria-label={t("common.slideZoomAria", { n: i + 1 })}
          >
            {slide.imageBase64 ? (
              <img src={`data:image/png;base64,${slide.imageBase64}`} alt={t("common.slide", { n: i + 1 })} className="w-full object-cover" />
            ) : (
              <div className="aspect-video bg-surface flex items-center justify-center text-xs text-muted-soft">{t("common.loadingImage")}</div>
            )}
            {slide.unchanged && (
              <span className="absolute top-1 left-1 rounded-full border border-warn-border bg-warn-bg px-1.5 py-0.5 text-3xs font-medium text-warn-strong">
                {t("translationReview.unchangedBadge")}
              </span>
            )}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
              <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-xs font-medium text-foreground-soft px-2 py-1 rounded transition-opacity">
                {t("common.slide", { n: i + 1 })}
              </span>
            </div>
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 mb-4">
        <button
          onClick={async () => setDownloadFailed(!(await onDownloadTranslatedPptx()))}
          className="w-full px-4 py-2 text-sm text-kb border border-kb rounded-md hover:bg-kb/5 transition-colors flex items-center justify-center gap-2"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          {t("translationReview.downloadPptx")}
        </button>
        {downloadFailed && (
          <p className="text-sm text-error" role="alert">
            {t("error.downloadFailed")}
          </p>
        )}

        <div className="relative">
          <label
            className={`block w-full px-4 py-2 text-sm text-foreground-soft border border-border rounded-md transition-colors text-center ${
              demo ? "opacity-60 cursor-not-allowed" : "hover:bg-surface cursor-pointer"
            }`}
            title={demo ? tDemo("keinHochladen") : undefined}
          >
            {loading ? t("translationReview.uploading") : t("translationReview.uploadCorrected")}
            <input
              type="file"
              accept=".pptx"
              className="hidden"
              disabled={loading || demo}
              onClick={(e) => { e.currentTarget.value = ""; }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUploadCorrectedPptx(f);
              }}
            />
          </label>
          {demo && <p className="mt-1 text-xs text-muted-soft">{tDemo("keinHochladen")}</p>}
          {correctedFileName && (
            <StatusMark tone="success" className="mt-2 text-sm">
              {t("translationReview.uploaded", { name: correctedFileName })}
            </StatusMark>
          )}
        </div>
      </div>

      {uploadFehler && (
        <div className="mb-4 rounded-lg border border-error-border bg-error-bg px-4 py-3" role="alert">
          {istFolienzahlFehler && (
            <p className="text-sm font-medium text-error-strong">{t("translationReview.folienzahlTitel")}</p>
          )}
          <p className="mt-0.5 text-sm text-error">{uploadFehler}</p>
        </div>
      )}

      <StepFooter
        onBack={onBack}
        nextLabel={t(skipTranslation ? "translationReview.weiterOhneUebersetzung" : "translationReview.acceptAndNext")}
        onNext={onAcceptAndNext}
        nextDisabled={loading}
      />
    </section>
  );
}
