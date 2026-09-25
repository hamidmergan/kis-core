export type Step = "content" | "slides" | "done";
export const STEPS = ["content", "slides", "done"] as const;

export type SourceMode = "files" | "module";
export type Language = "de" | "en";
// Mirrors limits.py: PRAESENTATION_MIN_SLIDES and PRAESENTATION_MAX_SLIDES, the model picks its own count inside them.
export const MIN_SLIDES = 3;
export const MAX_SLIDES = 30;
// Mirrors schemas.py: MAX_TEXT_ITEMS, MAX_TABLE_ROWS, MAX_CHART_CATEGORIES, MAX_NOTES_CHARS, MAX_SERIES_NAME_CHARS, MAX_PROMPT_CHARS, MAX_TITLE_CHARS, MAX_GIST_CHARS.
export const MAX_ITEMS = 8;
export const MAX_ROWS = 6;
export const MAX_CATEGORIES = 6;
export const MAX_NOTES = 1500;
export const MAX_SERIES_NAME = 60;
export const MAX_PROMPT = 600;
export const MAX_TITLE = 120;
export const MAX_GIST = 300;

export interface Source {
  mode: SourceMode;
  files: File[];
  moduleId: string;
  sourceIds: string[];
}

export interface OutlineRow {
  id: string;
  role: string;
  title: string;
  gist: string;
}

export interface Outline {
  title: string;
  subtitle: string;
  rows: OutlineRow[];
}

export interface Series {
  name: string;
  values: number[];
}

export type BodyKind = "bullets" | "table" | "chart" | "image" | "cards" | "bars" | "highlight";

export interface Card {
  icon: string;
  title: string;
  text: string;
}

/** One labelled bar, its length set by value, its label by text or the plain number. */
export interface Bar {
  label: string;
  value: number;
  text: string;
}

export interface Body {
  kind: BodyKind;
  items: string[];
  header: string[];
  rows: string[][];
  chart_type: string;
  categories: string[];
  series: Series[];
  prompt: string;
  cards: Card[];
  bars: Bar[];
  key: string;
  text: string;
  emphasis: string;
}

export interface Column {
  heading: string;
  items: string[];
}

/** The filled slide, the unit the backend builds and previews. */
export interface Slide {
  id: string;
  role: string;
  layout: number | null;
  title: string;
  subtitle: string;
  body: Body | null;
  columns: Column[];
  images: { prompt: string }[];
  notes: string;
}

export interface Vorlage {
  id: string;
  name: string;
  stiltext: string;
  system: boolean;
  roles: string[];
  hasImages: boolean;
}

export interface JobProgress {
  step?: string;
  current?: number;
  total?: number;
  /** True only in the last run, the one that finishes the file and needs nothing more from the person. */
  final?: boolean;
}

/** Mirrors schemas.bildstellen: the picture descriptions of a slide in the order the tool numbers them. */
export function bildPrompts(s: Slide): string[] {
  const alle = s.images.map((i) => i.prompt);
  if (s.body && s.body.kind === "image") alle.push(s.body.prompt);
  return alle;
}

export type JobStatus =
  | "idle" | "pending" | "running" | "awaiting_user" | "success" | "failed" | "waiting_retry" | "paused";

export interface PraesentationState {
  step: Step;
  maxReached: number;
  source: Source;
  instructions: string;
  /** Who gives the talk, shown on the cover when set. */
  presenter: string;
  language: Language;
  notes: boolean;
  /** Whether those notes go into the built file, decided in the slides step. */
  notesInclude: boolean;
  templateId: string;
  jobUuid: string | null;
  jobStatus: JobStatus;
  progress: JobProgress | null;
  error: string;
  outline: Outline | null;
  slides: Slide[];
  /** Slide ids with a preview, and a counter per id to bust the browser cache after an edit. */
  previews: Record<string, number>;
  missingImages: string[];
  hasDeck: boolean;
  templateFallback: boolean;
  starting: boolean;
}
