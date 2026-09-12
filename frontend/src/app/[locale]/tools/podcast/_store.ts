import type { Language, Length, PersonCount, Person, SourceMode, Step, Style } from "./_types";

const KEY = "kis_podcast";
const VERSION = 2;

/** What survives a closed tab: the job and the form, never the files. */
export interface Stored {
  jobUuid: string | null;
  step: Step;
  mode: SourceMode;
  text: string;
  moduleId: string;
  sourceIds: string[];
  instructions: string;
  language: Language;
  count: PersonCount;
  persons: Person[];
  length: Length;
  style: Style;
}

export function loadStored(): Stored | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { v?: number; state?: Stored };
    return parsed.v === VERSION && parsed.state ? parsed.state : null;
  } catch {
    return null;
  }
}

export function saveStored(state: Stored): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ v: VERSION, state }));
  } catch {
    // Storage may be blocked, the page still works without it.
  }
}

export function clearStored(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
