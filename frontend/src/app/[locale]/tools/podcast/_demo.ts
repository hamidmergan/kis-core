import type { PodcastView, Stimmprobe } from "./_api";
import type { JobProgress, Line } from "./_types";

/** The fixed material of the demo run, shown in the first step instead of a choice. */
export interface DemoMaterial {
  workspace: string;
  files: string[];
}

export type DemoView = PodcastView & DemoMaterial & { seconds: number | null; vergleich?: Stimmprobe[] };

/** One moment of the simulated run: what the job reports, the draft so far, and how long it stays. */
export interface DemoMoment {
  progress: JobProgress;
  draft: Line[];
  ms: number;
}

// Contributions per written part, and milliseconds each kind of moment stays up.
const TEIL = 7;
const DAUER = { teil: 900, beitrag: 250, montage: 1200 };

/** The script written part by part, each part readable as soon as it is done. */
export function demoSkript(lines: Line[]): DemoMoment[] {
  const total = Math.max(1, Math.ceil(lines.length / TEIL));
  return Array.from({ length: total }, (_, i) => ({
    progress: { step: "script", part: i + 1, total },
    draft: lines.slice(0, (i + 1) * TEIL),
    ms: DAUER.teil,
  }));
}

/** Every contribution voiced one after the other, then the parts are put together. */
export function demoVertonung(lines: Line[]): DemoMoment[] {
  const beitraege = lines.map((_, k) => ({
    progress: { step: "tts", fertig: Array.from({ length: k + 1 }, (_, i) => i) },
    draft: [],
    ms: DAUER.beitrag,
  }));
  return [...beitraege, { progress: { step: "montage" }, draft: [], ms: DAUER.montage }];
}

export function warte(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const zeit = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(zeit);
      reject(new DOMException("aborted", "AbortError"));
    });
  });
}
