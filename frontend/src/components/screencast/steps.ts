import type { ScreencastStep } from "@/types";

export const STEP_KEYS = [
  "upload",
  "translate",
  "review",
  "instructions",
  "scripts",
  "settings",
  "rendering",
  "done",
] as const;

export function stepToIndex(step: ScreencastStep): number {
  switch (step) {
    case "upload":
      return 0;
    case "translating":
      return 1;
    case "translation-review":
      return 2;
    case "user-prompt":
      return 3;
    case "generating-scripts":
    case "script-review":
      return 4;
    case "tts-settings":
      return 5;
    case "rendering":
      return 6;
    case "done":
      return 7;
    default:
      return 0;
  }
}

/** Only these steps may be re-entered, everything else is upload or a waiting page. */
export function indexToStep(index: number): ScreencastStep | null {
  switch (index) {
    case 2:
      return "translation-review";
    case 3:
      return "user-prompt";
    case 4:
      return "script-review";
    case 5:
      return "tts-settings";
    case 6:
      return "rendering";
    case 7:
      return "done";
    default:
      return null;
  }
}

/** From the finished video the first step opens empty, like a new screencast. */
export const startsAnew = (index: number, step: ScreencastStep): boolean => index === 0 && step === "done";

/** These steps are closed for good, not just at the moment. */
export function nieBetretbar(index: number, skipTranslation: boolean): boolean {
  if (skipTranslation && index === 1) return true;
  return indexToStep(index) === null;
}

/** The one rule that progress bar and footer answer alike. */
export function istErreichbar(
  index: number,
  maxReachedIdx: number,
  skipTranslation: boolean,
  step: ScreencastStep,
  hatErgebnis = false,
): boolean {
  if (step === "generating-scripts") return false;
  // During the run the waiting page is binding, with a finished video no longer.
  if (step === "rendering" && !hatErgebnis) return false;
  if (index === 6 && step !== "done" && !hatErgebnis) return false;
  if (index > maxReachedIdx) return false;
  if (skipTranslation && index === 1) return false;
  return indexToStep(index) !== null;
}

/** The next enterable step to the left, waiting pages are skipped. */
export function vorherErreichbar(
  index: number,
  maxReachedIdx: number,
  skipTranslation: boolean,
  step: ScreencastStep,
  hatErgebnis = false,
): number | null {
  for (let i = index - 1; i >= 0; i--) {
    if (istErreichbar(i, maxReachedIdx, skipTranslation, step, hatErgebnis)) return i;
  }
  return null;
}
