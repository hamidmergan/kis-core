export type Step = "content" | "cast" | "script" | "voicing" | "done";
export const STEPS = ["content", "cast", "script", "voicing", "done"] as const;

export type SourceMode = "text" | "files" | "module";
export type Language = "de" | "en";
export type Length = "short" | "medium" | "long";
export type Style = "teaching" | "casual" | "interview";
export type Role = "host" | "expert" | "student" | "critic";
export const ROLES: readonly Role[] = ["host", "expert", "student", "critic"];
export type PersonCount = 1 | 2 | 3 | 4;

export interface Person {
  name: string;
  role: Role;
  voiceId: string;
}

/** audioOf keeps the text at the time of voicing, so an edit shows up as a difference. */
export interface Line {
  id: string;
  speaker: number;
  text: string;
  audioOf: string | null;
}

export type RunStatus = "idle" | "running" | "failed" | "done";

export interface Run {
  status: RunStatus;
  failedId: string | null;
  /** The mock fails exactly once, this remembers that it already did. */
  failedOnce: boolean;
  voicedThisRun: number;
  /** Lines that already had audio when the run started. */
  keptIds: string[];
  cancelled: boolean;
}

export interface Source {
  mode: SourceMode;
  text: string;
  files: string[];
  moduleId: string;
  sourceIds: string[];
}

export interface PodcastState {
  step: Step;
  maxReached: number;
  source: Source;
  instructions: string;
  language: Language;
  count: PersonCount;
  persons: Person[];
  length: Length;
  style: Style;
  generating: boolean;
  lines: Line[];
  run: Run;
}
