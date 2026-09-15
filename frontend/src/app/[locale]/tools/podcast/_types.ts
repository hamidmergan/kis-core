export type Step = "content" | "cast" | "script" | "voicing" | "done";
export const STEPS = ["content", "cast", "script", "voicing", "done"] as const;

export type SourceMode = "files" | "module" | "blank";
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
  /** Voices may come from different providers, so each person names their own. */
  providerId: number;
}

/** One contribution of one person, the unit the backend voices. */
export interface Line {
  id: string;
  speaker: number;
  text: string;
}

/** What the job reports while it works, straight from the task. */
export interface JobProgress {
  step?: string;
  current?: number;
  total?: number;
  /** Indices of contributions that carry audio right now. */
  fertig?: number[];
  /** Indices that already had audio when this run started. */
  behalten?: number[];
}

export type JobStatus = "idle" | "pending" | "running" | "awaiting_user" | "success" | "failed";

export interface Source {
  mode: SourceMode;
  /** Only alive until the job starts, files never reach the browser storage. */
  files: File[];
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
  /** Speaking tempo of every voice, the same range the screencast offers. */
  speed: number;
  jobUuid: string | null;
  jobStatus: JobStatus;
  progress: JobProgress | null;
  error: string;
  lines: Line[];
  /** Written by hand from an empty script, so no model is asked anywhere. */
  selfWritten: boolean;
  /** The instruction named something the material does not cover. */
  instructionUnmatched: boolean;
  /** Ids whose audio matches their current text, seeded by the server. */
  voicedIds: string[];
  /** Measured running time of the finished file, the estimate only stands in until then. */
  seconds: number | null;
  /** True while the start call is in flight, before there is a job to poll. */
  starting: boolean;
}
