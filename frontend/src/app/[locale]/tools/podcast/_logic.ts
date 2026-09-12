import { STEPS, type Line, type PodcastState, type Source, type Step } from "./_types";

/** Spoken words per minute, the same figure the backend plans the length with. */
const WORDS_PER_MINUTE = 140;

export const stepIndex = (step: Step): number => STEPS.indexOf(step);

export const wordCount = (text: string): number => text.trim().split(/\s+/).filter(Boolean).length;
export const wordsOf = (lines: Line[]): number => lines.reduce((n, l) => n + wordCount(l.text), 0);
export const minutesOf = (lines: Line[]): number => Math.max(1, Math.round(wordsOf(lines) / WORDS_PER_MINUTE));

/** A contribution needs a voice as long as the server has none for this text. */
export const needsVoice = (line: Line, voicedIds: readonly string[]): boolean => !voicedIds.includes(line.id);
export const linesToVoice = (lines: Line[], voicedIds: readonly string[]): Line[] =>
  lines.filter((l) => needsVoice(l, voicedIds));

export function hasContent(source: Source): boolean {
  if (source.mode === "text") return source.text.trim().length > 0;
  if (source.mode === "files") return source.files.length > 0;
  return source.moduleId !== "" && source.sourceIds.length > 0;
}

export const isBusy = (state: PodcastState): boolean =>
  state.starting || state.jobStatus === "pending" || state.jobStatus === "running";

/** The number in "Beitrag 5 konnte nicht vertont werden", read back from the message. */
export function failedLineIndex(error: string): number {
  const treffer = error.match(/(\d+)/);
  return treffer ? Number(treffer[1]) - 1 : -1;
}

/** Which stepper entries can be clicked right now. */
export function reachable(index: number, state: PodcastState): boolean {
  if (index === stepIndex(state.step)) return false;
  if (isBusy(state)) return false;
  if (index > state.maxReached) return false;
  if (index === stepIndex("voicing")) return state.progress?.fertig?.length ? true : state.jobStatus === "failed";
  if (index === stepIndex("done")) return state.jobStatus === "success";
  // Content and cast are history once the job exists, the script stays open.
  if (index <= stepIndex("cast")) return state.jobUuid === null;
  return true;
}
