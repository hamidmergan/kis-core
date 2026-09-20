import { MAX_SLIDES, MIN_SLIDES, STEPS, type JobStatus, type Outline, type PraesentationState, type Source, type Step } from "./_types";

export const LAEUFT: ReadonlySet<JobStatus> = new Set(["pending", "running", "waiting_retry"]);

export const stepIndex = (step: Step): number => STEPS.indexOf(step);

export function hasContent(source: Source): boolean {
  if (source.mode === "files") return source.files.length > 0;
  return source.moduleId !== "" && source.sourceIds.length > 0;
}

/** Once slides exist the outline follows the built deck, so the floor drops and only the hard cap applies. */
export function rowCountOk(outline: Outline | null, hasSlides = false): boolean {
  if (!outline) return false;
  const lo = hasSlides ? 1 : MIN_SLIDES;
  return outline.rows.length >= lo && outline.rows.length <= MAX_SLIDES;
}

export const isBusy = (state: PraesentationState): boolean => state.starting || LAEUFT.has(state.jobStatus);

/** Which step a click on the stepper may open. */
export function reachable(index: number, state: PraesentationState): boolean {
  if (index === stepIndex(state.step)) return false;
  if (isBusy(state)) return false;
  if (index > state.maxReached) return false;
  if (index === stepIndex("content")) return state.jobUuid === null;
  if (index === stepIndex("done")) return state.jobStatus === "success";
  if (index === stepIndex("slides")) return state.slides.length > 0;
  return true;
}

/** With the job the content step is gone for good, the later steps stay open. */
export const closedForGood = (index: number, state: PraesentationState): boolean =>
  index === stepIndex("content") && state.jobUuid !== null;

/** A new slide needs a heading or an instruction, either one is enough. */
export const kannEinfuegen = (titel: string, anweisung: string): boolean =>
  titel.trim() !== "" || anweisung.trim() !== "";
