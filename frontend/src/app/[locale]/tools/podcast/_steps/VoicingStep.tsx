"use client";

import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import BeitragVorschau from "../_components/BeitragVorschau";
import { failedLineIndex, linesToVoice, needsVoice } from "../_logic";
import type { JobProgress, JobStatus, Line, Person } from "../_types";

const cancelIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

interface VoicingStepProps {
  jobUuid: string | null;
  lines: Line[];
  persons: Person[];
  voicedIds: string[];
  jobStatus: JobStatus;
  progress: JobProgress | null;
  error: string;
  onResume: () => void;
  onCancel: () => void;
  onBackToScript: () => void;
  onWeiter: () => void;
  /** The prepared demo run, nothing runs in the background there. */
  demo?: boolean;
}

export default function VoicingStep(props: VoicingStepProps) {
  const { jobUuid, lines, persons, voicedIds, jobStatus, progress, error,
          onResume, onCancel, onBackToScript, onWeiter, demo = false } = props;
  const t = useTranslations("tools.podcast.voicing");
  const tv = useTranslations("tools.podcast.vorschau");
  const tScript = useTranslations("tools.podcast.script");
  const tCommon = useTranslations("tools.podcast.common");

  const running = jobStatus === "pending" || jobStatus === "running";
  const wartet = jobStatus === "waiting_retry";
  const angehalten = jobStatus === "paused";
  const gestoert = jobStatus === "failed" || angehalten;
  const rueckblick = !running && !wartet && !gestoert;
  const done = running ? (progress?.fertig?.length ?? 0) : lines.filter((l) => !needsVoice(l, voicedIds)).length;
  const failedIndex = gestoert ? failedLineIndex(error) : -1;
  const offen = linesToVoice(lines, voicedIds).length;
  const schritt = progress?.step ?? "";

  return (
    <section className="animate-[fadeIn_0.3s_ease-out] py-4" role="status" aria-live="polite">
      <div className="text-center">
        {rueckblick ? (
          <>
            <h2 className="text-lg font-bold">{tv("rueckblick")}</h2>
            <p className="text-sm text-muted mt-1">{tv("rueckblickHinweis")}</p>
          </>
        ) : (
          <>
            {(running || wartet) && <Spinner size="lg" className="justify-center mb-4" />}
            <h2 className="text-lg font-bold">{t("heading")}</h2>
            {running && (
              <p className="text-sm text-foreground-soft mt-1">
                {schritt === "montage" || schritt === "saving"
                  ? t("assembling")
                  : t("progress", { done, total: lines.length })}
              </p>
            )}
            {wartet && <p className="text-sm text-foreground-soft mt-1">{t("waitingRetry")}</p>}
          </>
        )}
      </div>

      {(running || wartet) && !demo && <BackgroundHint />}

      {gestoert && (
        <div className="mt-6 rounded-lg border border-error-border bg-error-bg px-4 py-3" role="alert">
          <p className="text-sm font-medium text-error-strong">
            {angehalten
              ? t("pausedTitle")
              : failedIndex >= 0 ? t("failedTitle", { n: failedIndex + 1 }) : t("failedGeneric")}
          </p>
          <p className="text-sm text-error mt-0.5">{error || t("failedBody", { done })}</p>
          <div className="flex flex-wrap gap-3 mt-3">
            <button type="button" onClick={onResume} className="px-4 py-2 text-sm btn-primary rounded-lg">
              {angehalten
                ? t("continue")
                : failedIndex >= 0 ? t("resume", { n: failedIndex + 1 }) : t("resumeGeneric")}
            </button>
            <button type="button" onClick={onBackToScript} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
              {t("backToScript")}
            </button>
          </div>
        </div>
      )}

      <BeitragVorschau
        jobUuid={jobUuid}
        lines={lines}
        persons={persons}
        voicedIds={voicedIds}
        progress={progress}
        running={running}
        failedIndex={failedIndex}
        rueckblick={rueckblick}
      />

      <div className="flex justify-center mt-6">
        {running ? (
          <button type="button" onClick={onCancel} className="btn-cancel px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2">
            {cancelIcon}
            {tCommon("cancel")}
          </button>
        ) : rueckblick && offen > 0 ? (
          <button type="button" onClick={onResume} className="px-6 py-2 text-sm btn-primary rounded-md transition-colors select-none">
            {tScript("nextChanged", { n: offen })}
          </button>
        ) : rueckblick ? (
          <button type="button" onClick={onWeiter} className="px-6 py-2 text-sm btn-primary rounded-md transition-colors select-none">
            {tv("zumErgebnis")}
          </button>
        ) : null}
      </div>
    </section>
  );
}
