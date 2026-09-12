import { STEPS, type Line, type PodcastState, type Run, type Source, type Step } from "./_types";

/** The mock fails once, at the fifth line of the first run, so the resume is visible. */
export const FAIL_AT = 4;
/** Spoken words per minute for the length estimate. */
const WORDS_PER_MINUTE = 140;

export const stepIndex = (step: Step): number => STEPS.indexOf(step);

export const needsVoice = (line: Line): boolean => line.audioOf !== line.text;
export const linesToVoice = (lines: Line[]): Line[] => lines.filter(needsVoice);
export const wordCount = (text: string): number => text.trim().split(/\s+/).filter(Boolean).length;
export const wordsOf = (lines: Line[]): number => lines.reduce((n, l) => n + wordCount(l.text), 0);
export const minutesOf = (lines: Line[]): number => Math.max(1, Math.round(wordsOf(lines) / WORDS_PER_MINUTE));

export function hasContent(source: Source): boolean {
  if (source.mode === "text") return source.text.trim().length > 0;
  if (source.mode === "files") return source.files.length > 0;
  return source.moduleId !== "" && source.sourceIds.length > 0;
}

export type Tick = { kind: "done" } | { kind: "fail"; id: string } | { kind: "voiced"; lines: Line[] };

/** One step of the simulated voicing: the next unvoiced line gets its audio, or the run fails once. */
export function nextTick(lines: Line[], run: Run): Tick {
  const next = lines.find(needsVoice);
  if (!next) return { kind: "done" };
  if (!run.failedOnce && run.voicedThisRun === FAIL_AT && linesToVoice(lines).length > 2) {
    return { kind: "fail", id: next.id };
  }
  return { kind: "voiced", lines: lines.map((l) => (l.id === next.id ? { ...l, audioOf: l.text } : l)) };
}

/** Which stepper entries can be clicked right now. */
export function reachable(index: number, state: PodcastState): boolean {
  if (index === stepIndex(state.step)) return false;
  if (state.generating || state.run.status === "running") return false;
  if (index > state.maxReached) return false;
  if (index === stepIndex("voicing")) return state.run.status !== "idle";
  if (index === stepIndex("done")) return state.run.status === "done";
  return true;
}

/** A rephrasing stand-in: the last sentence moves to the front. */
export function rephrase(text: string): string {
  const parts = text.match(/[^.!?]+[.!?]+/g)?.map((s) => s.trim()) ?? [];
  if (parts.length < 2) return text;
  return [parts[parts.length - 1], ...parts.slice(0, -1)].join(" ");
}
