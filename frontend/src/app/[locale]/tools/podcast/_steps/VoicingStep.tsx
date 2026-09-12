"use client";

import { useTranslations } from "next-intl";
import { Info } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import BeitragVorschau from "../_components/BeitragVorschau";
import { linesToVoice, needsVoice } from "../_logic";
import type { Line, Person, Run } from "../_types";

const cancelIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

interface VoicingStepProps {
  lines: Line[];
  persons: Person[];
  run: Run;
  onResume: () => void;
  onCancel: () => void;
  onBackToScript: () => void;
  onUpdate: (id: string, text: string) => void;
  onVoice: () => void;
  onWeiter: () => void;
}

export default function VoicingStep({ lines, persons, run, onResume, onCancel, onBackToScript, onUpdate, onVoice, onWeiter }: VoicingStepProps) {
  const t = useTranslations("tools.podcast.voicing");
  const tv = useTranslations("tools.podcast.vorschau");
  const tScript = useTranslations("tools.podcast.script");
  const tCommon = useTranslations("tools.podcast.common");
  const done = lines.filter((l) => !needsVoice(l)).length;
  const failedIndex = lines.findIndex((l) => l.id === run.failedId);
  // The run is over, the page only serves for listening again and changing single lines.
  const rueckblick = run.status === "done";
  const toVoice = linesToVoice(lines).length;

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
            {run.status === "running" && <Spinner size="lg" className="justify-center mb-4" />}
            <h2 className="text-lg font-bold">{t("heading")}</h2>
          </>
        )}
      </div>

      {run.status === "running" && (
        <p className="mt-6 flex items-start gap-2 rounded-lg bg-surface px-4 py-3 text-sm text-foreground-soft">
          <Info size={14} className="mt-0.5 flex-shrink-0 text-muted-soft" aria-hidden="true" />
          {t("background")}
        </p>
      )}

      {run.status === "failed" && (
        <div className="mt-6 rounded-lg border border-error-border bg-error-bg px-4 py-3" role="alert">
          <p className="text-sm font-medium text-error-strong">{t("failedTitle", { n: failedIndex + 1 })}</p>
          <p className="text-sm text-error mt-0.5">{t("failedBody", { done })}</p>
          <div className="flex flex-wrap gap-3 mt-3">
            <button type="button" onClick={onResume} className="px-4 py-2 text-sm btn-primary rounded-lg">
              {t("resume", { n: failedIndex + 1 })}
            </button>
            <button type="button" onClick={onBackToScript} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
              {t("backToScript")}
            </button>
          </div>
        </div>
      )}

      <BeitragVorschau lines={lines} persons={persons} run={run} rueckblick={rueckblick} onUpdate={rueckblick ? onUpdate : undefined} />

      <div className="flex justify-center mt-6">
        {run.status === "running" ? (
          <button type="button" onClick={onCancel} className="btn-cancel px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2">
            {cancelIcon}
            {tCommon("cancel")}
          </button>
        ) : rueckblick && toVoice > 0 ? (
          <button type="button" onClick={onVoice} className="px-6 py-2 text-sm btn-primary rounded-md transition-colors select-none">
            {tScript("nextChanged", { n: toVoice })}
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
