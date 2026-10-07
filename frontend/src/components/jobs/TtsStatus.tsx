"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { SpeakerHigh } from "@phosphor-icons/react";
import type { TTSState } from "@/types";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import BackgroundHint from "@/components/tools/BackgroundHint";

interface TtsStatusProps {
  state: TTSState;
  fileName?: string;
  audioUrl?: string;
  errorMessage?: string;
  onDownload?: () => void;
  onReset?: () => void;
  /** Back to the input after an error, the text stays. */
  onRetry?: () => void;
  onContinue?: () => void;
  /** The info icon of the finished result, next to its status. */
  info?: ReactNode;
  /** The delete button of the finished result, in its button row. */
  loeschen?: ReactNode;
}

export default function TtsStatus({
  state,
  fileName,
  audioUrl,
  errorMessage,
  onDownload,
  onReset,
  onRetry,
  onContinue,
  info,
  loeschen,
}: TtsStatusProps) {
  const t = useTranslations("tools.tts.status");
  if (state === "idle") return null;

  return (
    <>
      {(state === "uploading" || state === "processing") && (
        <>
          <BackgroundHint />
          <div className="flex items-center gap-3">
            <Spinner />
            <span className="text-sm text-foreground-soft">
              {state === "uploading" ? t("uploadingFile") : t("generatingAudio")}
            </span>
          </div>
        </>
      )}

      {state === "done" && (
        <div className="flex flex-col items-center gap-4 text-center">
          {/* Status left, info icon at the far right, like the other tools. */}
          <div className="w-full flex items-center justify-between gap-2">
            <StatusMark tone="success" className="text-sm font-medium">{t("readyToPlay")}</StatusMark>
            {info}
          </div>

          {/* Audio player — consistent with the AIA media player */}
          {audioUrl && (
            <div className="w-full max-w-md flex flex-col items-center gap-4">
              <div
                className="w-24 h-24 rounded-full flex items-center justify-center"
                style={{ backgroundColor: "rgba(var(--kb-rgb),0.1)" }}
              >
                <SpeakerHigh size={40} weight="bold" style={{ color: "var(--kb)" }} />
              </div>
              {fileName && <span className="text-sm font-medium truncate max-w-full">{fileName}</span>}
              <audio src={audioUrl} controls className="w-full" />
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={onDownload}
              aria-label="MP3"
              className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              MP3
            </button>
            <button
              onClick={onReset}
              className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
            >
              {t("newAudio")}
            </button>
            {loeschen}
          </div>
        </div>
      )}

      {state === "paused" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-foreground">{t("pausedTitle")}</span>
          </div>
          {errorMessage && <p className="text-xs text-error">{errorMessage}</p>}
          <p className="text-xs text-muted">{t("pausedHint")}</p>
          <div className="flex gap-3">
            <button
              onClick={onContinue}
              className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
            >
              {t("continue")}
            </button>
            <button
              onClick={onReset}
              className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
            >
              {t("newAudio")}
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
            onClick={onRetry ?? onReset}
            aria-label={t("tryAgain")}
            className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
          >
            {t("tryAgain")}
          </button>
        </div>
      )}
    </>
  );
}
