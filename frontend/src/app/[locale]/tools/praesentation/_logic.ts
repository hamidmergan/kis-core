import {
  MAX_SLIDES, MIN_SLIDES, STEPS,
  type JobProgress, type JobStatus, type Outline, type OutlineRow, type PraesentationState, type Slide, type Source, type Step,
} from "./_types";

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
  if (index === stepIndex("preview")) return state.outline !== null || state.slides.length > 0;
  return true;
}

/** Where a job opened from the list belongs: a finalize and its result in done, everything else in the preview. */
export function schrittFuer(status: JobStatus, progress: JobProgress | null): Step {
  if (status === "success") return "done";
  if (status !== "awaiting_user" && progress?.final) return "done";
  return "preview";
}

/** The one line that says what the run is doing, as a message key and its numbers. */
export function fortschrittMeldung(status: JobStatus, progress: JobProgress | null): { key: string; values?: Record<string, number> } {
  if (status === "waiting_retry") return { key: "waitingRetry" };
  const zahlen = { done: progress?.current ?? 0, total: progress?.total ?? 0 };
  switch (progress?.step ?? "") {
    // The route reports "material", the reading task "lesen", a fresh start nothing yet.
    case "": case "material": case "lesen": return { key: "progressMaterial" };
    case "outline": return { key: "progressOutline" };
    case "texte": return zahlen.total ? { key: "progressTexts", values: zahlen } : { key: "progressTextsStart" };
    case "bilder": return zahlen.total ? { key: "progressImages", values: zahlen } : { key: "progressImagesStart" };
    case "vorschau": return { key: "progressPreview" };
    default: return { key: "progressBuild" };
  }
}

/** Mirrors media._bildplaetze: every picture a slide asks for, named the way the store numbers them. */
export function bildPlaetze(s: Slide): string[] {
  const plaetze = s.images.map((_, k) => String(k));
  if (s.body?.kind === "image") plaetze.push("body");
  return plaetze;
}

export interface Skizze {
  id: string;
  role: string;
  row: OutlineRow | null;
  /** Null while its text is still being written. */
  slide: Slide | null;
}

const RAHMEN = new Set(["deckblatt", "abschnitt", "abschluss"]);

/** A slide inserted later exists before its text does, it counts as written once it carries content. */
export const istGeschrieben = (s: Slide): boolean =>
  s.body !== null || s.columns.length > 0 || s.images.length > 0 || RAHMEN.has(s.role);

/** One card per planned slide, in the order of the outline, filled with the slide once it is written. */
export function skizzen(outline: Outline | null, slides: Slide[]): Skizze[] {
  const geschrieben = (s: Slide | undefined) => (s && istGeschrieben(s) ? s : null);
  const nachId = new Map(slides.map((s) => [s.id, s]));
  if (!outline) return slides.map((s) => ({ id: s.id, role: s.role, row: null, slide: geschrieben(s) }));
  return outline.rows.map((r) => ({ id: r.id, role: r.role, row: r, slide: geschrieben(nachId.get(r.id)) }));
}

/** With the job the content step is gone for good, the later steps stay open. */
export const closedForGood = (index: number, state: PraesentationState): boolean =>
  index === stepIndex("content") && state.jobUuid !== null;

/** A new slide needs a heading or an instruction, either one is enough. */
export const kannEinfuegen = (titel: string, anweisung: string): boolean =>
  titel.trim() !== "" || anweisung.trim() !== "";
