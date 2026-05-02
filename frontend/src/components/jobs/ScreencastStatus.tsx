"use client";

import { useTranslations } from "next-intl";
import type { ScreencastState } from "@/types";
import Spinner from "@/components/ui/Spinner";

interface ScreencastStatusProps {
  state: ScreencastState;
  fileName?: string;
  errorMessage?: string;
  progressLabel?: string;
  onDownload?: () => void;
  onReset?: () => void;
  onRetry?: () => void;
  hasZip?: boolean;
  onZipDownload?: () => void;
}

export default function ScreencastStatus({
  state,
  fileName,
  errorMessage,
  progressLabel,
  onDownload,
  onReset,
  onRetry,
  hasZip,
  onZipDownload,
}: ScreencastStatusProps) {
  const tCommon = useTranslations("common");
  const t = useTranslations("jobsStatus.screencast");

  if (state === "idle") return null;

  return (
    <div className="mt-6 rounded-lg border border-border-soft bg-background p-6" role="status" aria-live="polite">
      {(state === "uploading" || state === "processing") && (
        <div className="flex items-center gap-3">
          <Spinner />
          <div>
            <span className="text-sm text-foreground-soft">
              {state === "uploading" ? tCommon("uploadingFile") : (progressLabel || t("processing"))}
            </span>
            {state === "processing" && !progressLabel && (
              <p className="text-xs text-muted-soft mt-1">{t("processingHint")}</p>
            )}
          </div>
        </div>
      )}

      {state === "done" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-sm font-medium text-foreground">{tCommon("downloadReady")}</span>
          </div>
          {fileName && <p className="text-xs text-muted">{fileName}</p>}
          <div className="flex flex-wrap gap-3">
            <button
              onClick={onDownload}
              aria-label={t("mp4")}
              className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {t("mp4")}
            </button>
            {hasZip && (
              <button
                onClick={onZipDownload}
                aria-label={t("zipAllAria")}
                className="px-4 py-2 bg-background text-kb border border-kb text-sm rounded-md hover:bg-kb/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
              >
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                {t("zipAll")}
              </button>
            )}
            <button
              onClick={onReset}
              aria-label={tCommon("uploadNewAria")}
              className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
            >
              {tCommon("newFile")}
            </button>
          </div>
        </div>
      )}

      {state === "error" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            <span className="text-sm font-medium text-error-strong">{t("errorTitle")}</span>
          </div>
          {errorMessage && <p className="text-xs text-error">{errorMessage}</p>}
          {onRetry && (
            <p className="text-xs text-muted">
              {t.rich("retryHint", { b: (chunks) => <strong>{chunks}</strong> })}
            </p>
          )}
          <div className="flex gap-3">
            {onRetry && (
              <button
                onClick={onRetry}
                aria-label={tCommon("retryJobAria")}
                className="px-4 py-2 text-sm text-white bg-kb rounded-md hover:outline-2 hover:outline-kb focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
              >
                {tCommon("retry")}
              </button>
            )}
            <button
              onClick={onReset}
              aria-label={tCommon("uploadNewAria")}
              className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
            >
              {tCommon("newFile")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
