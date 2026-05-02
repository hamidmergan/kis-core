"use client";

import { useTranslations } from "next-intl";
import type { TranscriptionState } from "@/types";
import Spinner from "@/components/ui/Spinner";

interface TranscriptionStatusProps {
  state: TranscriptionState;
  fileName?: string;
  errorMessage?: string;
  onDownload?: () => void;
  onReset?: () => void;
}

export default function TranscriptionStatus({
  state,
  fileName,
  errorMessage,
  onDownload,
  onReset,
}: TranscriptionStatusProps) {
  const tCommon = useTranslations("common");
  const t = useTranslations("jobsStatus.transcription");

  if (state === "idle") return null;

  return (
    <div className="mt-6 rounded-lg border border-border-soft bg-background p-6" role="status" aria-live="polite">
      {(state === "uploading" || state === "processing") && (
        <div className="flex items-center gap-3">
          <Spinner />
          <span className="text-sm text-foreground-soft">
            {state === "uploading" ? tCommon("uploadingFile") : t("processing")}
          </span>
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
          <div className="flex gap-3">
            <button
              onClick={onDownload}
              aria-label={t("download")}
              className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {t("download")}
            </button>
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
          <button
            onClick={onReset}
            aria-label={tCommon("tryAgain")}
            className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
          >
            {tCommon("tryAgain")}
          </button>
        </div>
      )}
    </div>
  );
}
