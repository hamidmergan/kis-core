// Shared types of the assessment, the answer key stays on the server.

/** Fallback for the answer length until the real value arrives. */
export const DIAGNOSIS_ANSWER_MAX_CHARS = 2000;

/** Fallback for the question count until the real value arrives. */
export const DIAGNOSIS_QUESTION_COUNT = 12;

// The six levels, each as its own code.
export type CEFRLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export interface ChatTurn {
  role: "assistant" | "user";
  content: string;
  /** The shown options, already shuffled by the server. */
  options?: string[];
  /** Several options can be correct, then checkboxes are used. */
  multi?: boolean;
  /** A short answer means a single-line field, display only. */
  short?: boolean;
  /** The clicked options, missing for a typed answer. */
  selected?: string[];
}

/** The shape of a history entry, display fields stay in the browser. */
export function toTranscript(turns: ChatTurn[]): {
  role: ChatTurn["role"];
  content: string;
  options?: string[];
  selected?: string[];
}[] {
  return turns.map(({ role, content, options, selected }) => ({
    role,
    content,
    ...(options ? { options } : {}),
    ...(selected ? { selected } : {}),
  }));
}

export interface DiagnosisResult {
  level: CEFRLevel;
  /** Closing feedback, written in the workspace's diagnosis language. */
  message: string;
}

/** One turn of the diagnosis: the next question, or the final verdict. */
export type DiagnosisTurnResponse =
  | { done: false; message: string; options?: string[]; multi?: boolean; short?: boolean }
  | ({ done: true } & DiagnosisResult);
