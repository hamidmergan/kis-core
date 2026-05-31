"use client";

import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";

const cancelIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

export function TranslatingStep({
  skipTranslation,
  onCancel,
}: {
  skipTranslation: boolean;
  onCancel: () => void;
}) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft animate-pulse">
        {skipTranslation ? t("translating.preparing") : t("translating.translating")}
      </p>
      <p className="text-xs text-muted-soft mt-2">{t("translating.subtle")}</p>
      <button
        onClick={onCancel}
        className="btn-cancel mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2"
      >
        {cancelIcon}
        {t("common.cancel")}
      </button>
    </section>
  );
}

export function GeneratingScriptsStep({
  slideCount,
  onCancel,
}: {
  slideCount: number;
  onCancel: () => void;
}) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft animate-pulse">{t("generatingScripts.title")}</p>
      <p className="text-xs text-muted-soft mt-2">{t("generatingScripts.subtle", { n: slideCount })}</p>
      <button
        onClick={onCancel}
        className="btn-cancel mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2"
      >
        {cancelIcon}
        {t("common.cancel")}
      </button>
    </section>
  );
}

export function RenderingStep({
  renderProgressLabel,
  onCancel,
}: {
  renderProgressLabel: string;
  onCancel: () => void;
}) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft">{renderProgressLabel || t("rendering.fallback")}</p>
      {!renderProgressLabel && (
        <p className="text-xs text-muted-soft mt-2">{t("rendering.subtle")}</p>
      )}
      <button
        onClick={onCancel}
        className="btn-cancel mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2"
      >
        {cancelIcon}
        {t("common.cancel")}
      </button>
    </section>
  );
}

export function DoneStep({
  videoUrl,
  audioId,
  onDownloadMp4,
  onReset,
}: {
  videoUrl: string | null;
  audioId: string;
  onDownloadMp4: () => void;
  onReset: () => void;
}) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] py-8">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-success-bg flex items-center justify-center">
          <svg className="w-6 h-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold mb-2 text-center">{t("done.heading")}</h2>

      {videoUrl && (
        <div className="mb-6 rounded-lg overflow-hidden border border-border-soft">
          <video key={videoUrl} controls className="w-full">
            <source src={videoUrl} type="video/mp4" />
            {t("done.browserNoVideo")}
          </video>
        </div>
      )}

      <div className="flex justify-center gap-3 mb-4">
        <button
          onClick={onDownloadMp4}
          aria-label={t("done.downloadMp4Aria")}
          className="px-6 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          {t("done.downloadMp4Label")}
        </button>
        {audioId && (
          <a
            href={`/api/jobs/${audioId}/bundle`}
            download
            aria-label={t("done.downloadAllZipAria")}
            className="px-6 py-2 bg-background text-kb border-2 border-kb text-sm font-medium rounded-md hover:border-kb-dark transition-colors flex items-center gap-2"
          >
            <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            {t("done.downloadAllZipLabel")}
          </a>
        )}
      </div>

      <div className="flex justify-center">
        <button
          onClick={onReset}
          aria-label={t("done.newPresentationAria")}
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          {t("done.newPresentation")}
        </button>
      </div>
    </section>
  );
}

export function ErrorStep({
  errorMessage,
  failedRenderJobUuid,
  onRetry,
  onReset,
}: {
  errorMessage: string;
  failedRenderJobUuid: string | null;
  onRetry: () => void;
  onReset: () => void;
}) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-12">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-error-bg flex items-center justify-center">
          <svg className="w-6 h-6 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold text-error-strong mb-2">{t("error.heading")}</h2>
      {errorMessage && <p className="text-sm text-error mb-3">{errorMessage}</p>}
      {failedRenderJobUuid && (
        <p className="text-xs text-muted mb-5">
          {t.rich("error.retryHint", { strong: (chunks) => <strong>{chunks}</strong> })}
        </p>
      )}
      <div className="flex gap-3 justify-center">
        {failedRenderJobUuid && (
          <button
            onClick={onRetry}
            aria-label={t("error.retryAria")}
            className="px-6 py-2 text-sm text-white bg-kb rounded-md hover:outline-2 hover:outline-kb focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
          >
            {t("error.retry")}
          </button>
        )}
        <button
          onClick={onReset}
          aria-label={t("done.newPresentationAria")}
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          {t("done.newPresentation")}
        </button>
      </div>
    </section>
  );
}
