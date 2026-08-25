"use client";

import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { mitLaufStempel } from "../_utils";

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
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-20" role="status" aria-live="polite">
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
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-20" role="status" aria-live="polite">
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
  vorschau,
  rueckblick = false,
  onCancel,
  onWeiter,
}: {
  renderProgressLabel: string;
  vorschau?: React.ReactNode;
  /** Der Lauf ist durch, die Seite dient nur noch zum Nachhoeren. */
  rueckblick?: boolean;
  onCancel: () => void;
  onWeiter: () => void;
}) {
  const t = useTranslations("tools.screencast");
  const tv = useTranslations("tools.screencast.vorschau");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] py-10" role="status" aria-live="polite">
      <div className="text-center">
        {rueckblick ? (
          <h2 className="text-lg font-bold">{tv("rueckblick")}</h2>
        ) : (
          <>
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-foreground-soft">{renderProgressLabel || t("rendering.fallback")}</p>
            {!renderProgressLabel && (
              <p className="text-xs text-muted-soft mt-2">{t("rendering.subtle")}</p>
            )}
          </>
        )}
      </div>

      {vorschau}

      <div className="flex justify-center mt-6">
        {rueckblick ? (
          <button onClick={onWeiter} className="px-6 py-2 text-sm btn-primary rounded-md transition-colors select-none">
            {tv("zumErgebnis")}
          </button>
        ) : (
          <button
            onClick={onCancel}
            className="btn-cancel px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2"
          >
            {t("common.cancel")}
          </button>
        )}
      </div>
    </section>
  );
}

export function DoneStep({
  videoUrl,
  audioId,
  hasSubtitles = false,
  laufStempel,
  onDownloadMp4,
  onReset,
  onNeuVertonen,
}: {
  videoUrl: string | null;
  audioId: string;
  hasSubtitles?: boolean;
  laufStempel: string;
  onDownloadMp4: () => void;
  onReset: () => void;
  onNeuVertonen: () => void;
}) {
  const t = useTranslations("tools.screencast");
  // Der Link haengt bewusst nicht in der Seite, sonst startet der Ladebalken oben und laeuft endlos weiter.
  const onDownloadZip = () => {
    const a = document.createElement("a");
    a.href = `/api/jobs/${audioId}/bundle`;
    a.download = "";
    a.click();
  };
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] py-10">
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
            {hasSubtitles && audioId && (
              <track
                kind="subtitles"
                src={mitLaufStempel(`/api/jobs/${audioId}/subtitles`, laufStempel)}
                label={t("done.subtitleTrack")}
                default
              />
            )}
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
          <button
            type="button"
            onClick={onDownloadZip}
            aria-label={t("done.downloadAllZipAria")}
            className="px-6 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
          >
            <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            {t("done.downloadAllZipLabel")}
          </button>
        )}
      </div>

      <div className="flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={onNeuVertonen}
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          {t("done.neuVertonen")}
        </button>
        <button
          onClick={onReset}
          aria-label={t("done.newPresentationAria")}
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
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
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16">
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
