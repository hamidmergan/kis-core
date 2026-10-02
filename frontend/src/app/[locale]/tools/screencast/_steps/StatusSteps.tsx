"use client";

import { useLocale, useTranslations } from "next-intl";
import { ErgebnisInfoKnopf, useErgebnisAngaben, type Auftrag } from "@/components/jobs/ErgebnisInfo";
import { sprachName } from "@/lib/format";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import { mitLaufStempel } from "../_utils";

const cancelIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

export function TranslatingStep({
  skipTranslation,
  onCancel,
  ohneHintergrund = false,
}: {
  skipTranslation: boolean;
  onCancel: () => void;
  /** The demo runs nothing in the background. */
  ohneHintergrund?: boolean;
}) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-20" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft animate-pulse">
        {skipTranslation ? t("translating.preparing") : t("translating.translating")}
      </p>
      <p className="text-xs text-muted-soft mt-2">{t("translating.subtle")}</p>
      {!ohneHintergrund && <BackgroundHint />}
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
  ohneHintergrund = false,
}: {
  slideCount: number;
  onCancel: () => void;
  /** The demo runs nothing in the background. */
  ohneHintergrund?: boolean;
}) {
  const t = useTranslations("tools.screencast");
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-20" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft animate-pulse">{t("generatingScripts.title")}</p>
      <p className="text-xs text-muted-soft mt-2">{t("generatingScripts.subtle", { n: slideCount })}</p>
      {!ohneHintergrund && <BackgroundHint />}
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
  ohneHintergrund = false,
}: {
  renderProgressLabel: string;
  vorschau?: React.ReactNode;
  /** The run is done, the page only serves for listening again. */
  rueckblick?: boolean;
  onCancel: () => void;
  onWeiter: () => void;
  /** The demo runs nothing in the background. */
  ohneHintergrund?: boolean;
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
        {!rueckblick && !ohneHintergrund && <BackgroundHint />}
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
  zipUrl,
  demoAuftrag,
}: {
  videoUrl: string | null;
  audioId: string;
  hasSubtitles?: boolean;
  laufStempel: string;
  onDownloadMp4: () => void;
  onReset: () => void;
  onNeuVertonen: () => void;
  /** The demo bundles its prepared files elsewhere. */
  zipUrl?: string;
  /** The demo brings the info of its prepared video along. */
  demoAuftrag?: Auftrag | null;
}) {
  const t = useTranslations("tools.screencast");
  const tResult = useTranslations("common.result");
  const locale = useLocale();
  const gelesen = useErgebnisAngaben(demoAuftrag === undefined && audioId ? audioId : null);
  const auftrag = demoAuftrag === undefined ? gelesen : demoAuftrag;
  // The link deliberately does not sit in the page, otherwise the top loader runs forever.
  const onDownloadZip = () => {
    const a = document.createElement("a");
    a.href = zipUrl ?? `/api/jobs/${audioId}/bundle`;
    a.download = "";
    a.click();
  };
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] pt-3 sm:py-10">
      <div className="relative rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5">
      <div className="absolute top-3 right-3">
        <ErgebnisInfoKnopf auftrag={auftrag} zeilen={[
          { label: tResult("file"), wert: auftrag?.datei },
          { label: t("ttsSettings.providerLabel"), wert: auftrag?.angaben.anbieter },
          { label: tResult("language"), wert: sprachName(auftrag?.angaben.sprache, locale) },
          { label: t("ttsSettings.voiceLabel"), wert: auftrag?.angaben.stimme },
        ]} />
      </div>
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: "var(--kb)" }}>
          <svg className="w-6 h-6" style={{ color: "#fff" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
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

      {/* Desktop: downloads above the two side buttons. Phone: side buttons first, downloads pinned below. */}
      <div className="flex flex-col">
      <div className="order-last sm:order-none sticky bottom-0 z-30 -mx-4 -mb-4 rounded-b-xl px-4 py-3 mt-6 border-t border-border-soft bg-background grid grid-cols-2 gap-2 sm:static sm:mx-0 sm:px-0 sm:py-0 sm:mt-0 sm:mb-4 sm:border-0 sm:bg-transparent sm:flex sm:justify-center sm:gap-3">
        <button
          onClick={onDownloadMp4}
          aria-label={t("done.downloadMp4Aria")}
          className="px-6 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center justify-center gap-2"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          {t("done.downloadMp4Label")}
        </button>
        {(audioId || zipUrl) && (
          <button
            type="button"
            onClick={onDownloadZip}
            aria-label={t("done.downloadAllZipAria")}
            className="px-6 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center justify-center gap-2"
          >
            <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            {t("done.downloadAllZipLabel")}
          </button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row sm:flex-wrap sm:justify-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={onNeuVertonen}
          className="w-full sm:w-auto px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          {t("done.neuVertonen")}
        </button>
        <button
          onClick={onReset}
          className="w-full sm:w-auto px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          {t("done.newScreencast")}
        </button>
      </div>
      </div>
      </div>
    </section>
  );
}

export function ErrorStep({
  errorMessage,
  failedRenderJobUuid,
  paused = false,
  onRetry,
  onReset,
}: {
  errorMessage: string;
  failedRenderJobUuid: string | null;
  paused?: boolean;
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
      <h2 className="text-lg font-bold text-error-strong mb-2">
        {paused ? t("error.pausedHeading") : t("error.heading")}
      </h2>
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
            className="px-6 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
          >
            {paused ? t("error.continue") : t("error.retry")}
          </button>
        )}
        <button
          onClick={onReset}
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          {t("done.newScreencast")}
        </button>
      </div>
    </section>
  );
}
