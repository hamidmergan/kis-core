// The six CEFR steps in ladder order, shared by the level page and the test.
export const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;

export type CefrLevel = (typeof CEFR_LEVELS)[number];

/** True for every step up to and including the own level, that fills the ladder. */
export function isReached(step: CefrLevel, own: CefrLevel): boolean {
  return CEFR_LEVELS.indexOf(step) <= CEFR_LEVELS.indexOf(own);
}
