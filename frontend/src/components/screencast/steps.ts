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
