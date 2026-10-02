"use client";

import { useLocale, useTranslations } from "next-intl";
import { ErgebnisInfoKnopf, useErgebnisAngaben, type Auftrag } from "@/components/jobs/ErgebnisInfo";
import { sprachName } from "@/lib/format";
import { resultUrl, transcriptUrl } from "../_api";
import { linesToVoice, minutesOf } from "../_logic";
import { ROLES, type JobProgress, type JobStatus, type Line, type Person, type PersonCount, type Role } from "../_types";

const downloadIcon = (
  <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
  </svg>
);
const LINK = "px-6 py-2 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2";
const GHOST = "px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors";

interface DoneStepProps {
  jobUuid: string | null;
  lines: Line[];
  persons: Person[];
  count: PersonCount;
  voicedIds: string[];
  jobStatus: JobStatus;
  progress: JobProgress | null;
  seconds: number | null;
  onVoice: () => void;
  onEditScript: () => void;
  onReset: () => void;
  /** The demo brings its info along, a real run reads it from its job. */
  auftrag?: Auftrag;
}

export default function DoneStep(props: DoneStepProps) {
  const { jobUuid, lines, persons, count, voicedIds, jobStatus, progress, seconds,
          onVoice, onEditScript, onReset } = props;
  const locale = useLocale();
  const t = useTranslations("tools.podcast.done");
  const tScript = useTranslations("tools.podcast.script");
  const tPage = useTranslations("tools.podcast");
  const tCast = useTranslations("tools.podcast.cast");
  const tResult = useTranslations("common.result");
  // Read once the run is through, the info is written as its last step.
  const gelesen = useErgebnisAngaben(props.auftrag || jobStatus !== "success" ? null : jobUuid);
  const auftrag = props.auftrag ?? gelesen;
  const angaben = auftrag?.angaben;
  // The measured length once it exists, the estimate from the words until then.
  const minutes = seconds != null ? Math.max(1, Math.round(seconds / 60)) : minutesOf(lines);
  const offen = linesToVoice(lines, voicedIds).length;

  // The finished file is downloaded, not streamed: a link keeps the loader quiet.
  const speichern = (url: string, name: string) => {
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
  };

  return (
    <section className="animate-[fadeIn_0.3s_ease-out] pt-3 sm:py-10">
      <div className="relative rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5">
      <div className="absolute top-3 right-3">
        <ErgebnisInfoKnopf auftrag={auftrag} zeilen={[
          { label: t("infoProvider"), wert: angaben?.anbieter },
          { label: tResult("language"), wert: sprachName(angaben?.sprache, locale) },
          { label: t("infoCast"), wert: angaben?.besetzung?.map((b) => {
            const rolle = ROLES.includes(b.rolle as Role) ? tCast(`roles.${b.rolle as Role}`) : b.rolle;
            return `${b.name} (${rolle})${b.stimme ? `: ${b.stimme}` : ""}`;
          }).join("\n") },
          { label: tResult("sources"), wert: angaben?.material?.split(", ").join("\n") },
        ]} />
      </div>
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: "var(--kb)" }}>
          <svg className="w-6 h-6" style={{ color: "#fff" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold mb-1 text-center">{t("heading")}</h2>
      <p className="text-sm text-muted text-center mb-6">{t("summary", { minutes, lines: lines.length, count })}</p>

      {jobUuid && (
        <div className="mb-6">
          <div className="w-full max-w-md mx-auto">
            <audio key={`${jobUuid}-${voicedIds.length}`} controls className="w-full" src={resultUrl(jobUuid)}>
              {t("browserNoAudio")}
            </audio>
          </div>
        </div>
      )}

      {/* Desktop: downloads above the two side buttons. Phone: side buttons first, downloads pinned below. */}
      <div className="flex flex-col">
        <div className="order-last sm:order-none sticky bottom-0 z-30 -mx-4 -mb-4 rounded-b-xl px-4 py-3 mt-6 border-t border-border-soft bg-background grid grid-cols-2 gap-2 sm:static sm:mx-0 sm:px-0 sm:py-0 sm:mt-0 sm:mb-4 sm:border-0 sm:bg-transparent sm:flex sm:flex-wrap sm:justify-center sm:gap-3">
          <button type="button" onClick={() => jobUuid && speichern(resultUrl(jobUuid), "podcast.mp3")} className={`${LINK} justify-center`}>
            {downloadIcon}
            {t("download")}
          </button>
          <button type="button" onClick={() => jobUuid && speichern(transcriptUrl(jobUuid), "podcast.txt")} className={`${LINK} justify-center`}>
            {downloadIcon}
            {t("transcript")}
          </button>
        </div>

        <div className="flex flex-col sm:flex-row sm:flex-wrap sm:justify-center gap-2 sm:gap-3">
          <button type="button" onClick={onEditScript} className={`${GHOST} w-full sm:w-auto`}>
            {t("editScript")}
          </button>
          <button type="button" onClick={onReset} className={`${GHOST} w-full sm:w-auto`}>
            {tPage("newPodcast")}
          </button>
        </div>
      </div>
      </div>

      {offen > 0 && (
        <div className="flex justify-center mt-6 sm:mt-10">
          <button type="button" onClick={onVoice} className="px-6 py-2 text-sm btn-primary rounded-md transition-colors select-none">
            {tScript("nextChanged", { n: offen })}
          </button>
        </div>
      )}
    </section>
  );
}
