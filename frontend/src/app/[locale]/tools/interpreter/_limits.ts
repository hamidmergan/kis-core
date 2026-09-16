/**
 * The two ceilings of the interpreter: how long one recording may run and how much a
 * conversation may collect. Both are plain numbers here so they can be tested without a
 * microphone and stay in one place.
 */

/** A recording stops itself here, every window resends the whole audio so far. */
export const MAX_RECORDING_MS = 300_000;
/** From here the card says that the recording is about to end. */
export const ENDING_SOON_MS = 270_000;

export type RecordingPhase = "running" | "endingSoon" | "stop";

export function recordingPhase(elapsedMs: number): RecordingPhase {
  if (elapsedMs >= MAX_RECORDING_MS) return "stop";
  if (elapsedMs >= ENDING_SOON_MS) return "endingSoon";
  return "running";
}

/** A conversation ends by itself here, roughly an hour of real back and forth. */
export const SESSION_CHAR_LIMIT = 20_000;
/** From here the page warns that the conversation is nearly full. */
export const CHAR_WARN_AT = 18_000;

export type CharState = "ok" | "near" | "full";

/** What was said and typed on both sides, the translation does not count against anyone. */
export function countChars(turns: readonly { original: string }[]): number {
  return turns.reduce((sum, turn) => sum + turn.original.length, 0);
}

export function charState(chars: number): CharState {
  if (chars >= SESSION_CHAR_LIMIT) return "full";
  if (chars >= CHAR_WARN_AT) return "near";
  return "ok";
}
