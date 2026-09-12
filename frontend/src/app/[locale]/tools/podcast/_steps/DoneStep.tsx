"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { MicrophoneStage } from "@phosphor-icons/react";
import BeitragVorschau from "../_components/BeitragVorschau";
import { silentWavUrl } from "../_audio";
import { linesToVoice, minutesOf } from "../_logic";
import type { Line, Person, PersonCount, Run } from "../_types";

const downloadIcon = (
  <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
  </svg>
);

interface DoneStepProps {
  lines: Line[];
  persons: Person[];
  count: PersonCount;
  run: Run;
  onUpdate: (id: string, text: string) => void;
  onVoice: () => void;
  onEditScript: () => void;
  onReset: () => void;
}

export default function DoneStep({ lines, persons, count, run, onUpdate, onVoice, onEditScript, onReset }: DoneStepProps) {
  const t = useTranslations("tools.podcast.done");
  const tv = useTranslations("tools.podcast.vorschau");
  const tScript = useTranslations("tools.podcast.script");
  const tPage = useTranslations("tools.podcast");
  const minutes = minutesOf(lines);
  const toVoice = linesToVoice(lines).length;
  const [audioUrl, setAudioUrl] = useState("");

  // The mockup plays silence of the estimated length, the real build plays the MP3 from the job.
  useEffect(() => {
    const url = silentWavUrl(minutes * 60);
    setAudioUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [minutes]);

  const save = (href: string, name: string) => {
    const a = document.createElement("a");
    a.href = href;
    a.download = name;
    a.click();
  };
  const downloadTranscript = () => {
    const text = lines.map((l) => `${(persons[l.speaker] ?? persons[0]).name}: ${l.text}`).join("\n\n");
    const blob = new Blob([`${text}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    save(url, `${t("filename")}.txt`);
    URL.revokeObjectURL(url);
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
      <h2 className="text-lg font-bold mb-1 text-center">{t("heading")}</h2>
      <p className="text-sm text-muted text-center mb-6">{t("summary", { minutes, lines: lines.length, count })}</p>

      <div className="mb-6 rounded-lg border border-border-soft p-6">
        <div className="w-full max-w-md mx-auto flex flex-col items-center gap-4">
          <div className="w-24 h-24 rounded-full flex items-center justify-center" style={{ backgroundColor: "rgba(var(--kb-rgb),0.1)" }}>
            <MicrophoneStage size={40} weight="bold" style={{ color: "var(--kb)" }} />
          </div>
          {audioUrl && (
            <audio key={audioUrl} controls className="w-full" src={audioUrl}>
              {t("browserNoAudio")}
            </audio>
          )}
        </div>
      </div>

      <div className="flex flex-wrap justify-center gap-3 mb-4">
        <button
          type="button"
          onClick={() => audioUrl && save(audioUrl, `${t("filename")}.wav`)}
          className="px-6 py-2 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
        >
          {downloadIcon}
          {t("download")}
        </button>
        <button
          type="button"
          onClick={downloadTranscript}
          className="px-6 py-2 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
        >
          {downloadIcon}
          {t("transcript")}
        </button>
      </div>

      <div className="flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={onEditScript}
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          {t("editScript")}
        </button>
        <button
          type="button"
          onClick={onReset}
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          {tPage("newPodcast")}
        </button>
      </div>

      <div className="mt-10">
        <h3 className="text-base font-semibold">{tv("rueckblick")}</h3>
        <p className="text-sm text-muted mt-1">{tv("rueckblickHinweis")}</p>
        <BeitragVorschau lines={lines} persons={persons} run={run} rueckblick onUpdate={onUpdate} />
        {toVoice > 0 && (
          <div className="flex justify-center mt-6">
            <button type="button" onClick={onVoice} className="px-6 py-2 text-sm btn-primary rounded-md transition-colors select-none">
              {tScript("nextChanged", { n: toVoice })}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
