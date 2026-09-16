/** Which waiting line the chat shows, derived from what the stream has delivered so far. */

/** Nothing is shown below this, a shorter wait would only flash. */
export const GRACE_MS = 300;

/** Once a line is painted it stays this long, long enough to actually be read. */
export const MIN_MS = 1200;

export type PhaseKey = "searching" | "generating";

export interface PhaseInput {
  /** Milliseconds since the question was sent. */
  elapsedMs: number;
  /** When the qmap event arrived, which is when the search finished. */
  qmapAtMs: number | null;
  /** True as soon as the first word of the answer is there. */
  hasText: boolean;
  /** Selected text in the viewer, which answers without searching. */
  isPopup: boolean;
}

export function phaseAt({ elapsedMs, qmapAtMs, hasText, isPopup }: PhaseInput): PhaseKey | null {
  if (hasText) return null;
  if (elapsedMs < GRACE_MS) return null;
  if (isPopup) return "generating";
  if (qmapAtMs === null) return "searching";

  // A search that finished inside the grace period was never visible, so it owes no minimum time.
  const searchUntil = qmapAtMs > GRACE_MS ? Math.max(qmapAtMs, GRACE_MS + MIN_MS) : GRACE_MS;
  return elapsedMs < searchUntil ? "searching" : "generating";
}
