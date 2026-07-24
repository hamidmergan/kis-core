// Shared types for the CEFR chat diagnosis.
//
// There is no question list here any more. The questions are produced by the
// model from the admin-managed prompt, so the client only carries the transcript
// and the final verdict.

/** Mirrors MAX_MESSAGE_CHARS in backend/src/services/aia_diagnosis_chat.py.
 *  Kept in sync by hand: exceeding it comes back as a 422, not a friendly error. */
export const DIAGNOSIS_ANSWER_MAX_CHARS = 2000;

/** Mirrors QUESTION_COUNT in backend/src/services/aia_diagnosis_chat.py.
 *  The test is a fixed staircase of this many questions, one per task type; the
 *  UI uses it only for the "question X of N" counter. The backend is the
 *  authority on the length. */
export const DIAGNOSIS_QUESTION_COUNT = 8;

// Four outcomes only. "B1+" is everything above B1 (no language support needed);
// it renders as "Über B1". See VALID_LEVELS in aia_diagnosis_chat.py.
export type CEFRLevel = "A1" | "A2" | "B1" | "B1+";

/** Learner-facing label for a stored level. "B1+" has no CEFR glyph, so it uses
 *  the localized "Über B1" string; the plain bands show as themselves. */
export function levelLabel(level: string, aboveB1Label: string): string {
  return level === "B1+" ? aboveB1Label : level;
}
export type Skill = "grammar" | "vocabulary" | "reading" | "writing" | "pragmatics";

export interface ChatTurn {
  role: "assistant" | "user";
  content: string;
  /** Assistant only: the one-sentence response to the previous answer. Shown as
   *  its own bubble, but merged back into the content before the transcript goes
   *  to the model, so it can still see what it already said. */
  reaction?: string;
}

/** The wire shape of one transcript entry. The reaction lives in the content
 *  here: the split is a display concern, and a model that no longer sees its own
 *  openers starts repeating them. */
export function toTranscript(turns: ChatTurn[]): { role: ChatTurn["role"]; content: string }[] {
  return turns.map(({ role, content, reaction }) => ({
    role,
    content: reaction ? `${reaction}\n\n${content}` : content,
  }));
}

export interface DiagnosisResult {
  level: CEFRLevel;
  /** Closing feedback, written in the workspace's diagnosis language. */
  message: string;
  skill_scores: Record<Skill, number>;
}

/** One turn of the diagnosis: the next question, or the final verdict. */
export type DiagnosisTurnResponse =
  | { done: false; message: string; reaction?: string }
  | ({ done: true } & DiagnosisResult);
