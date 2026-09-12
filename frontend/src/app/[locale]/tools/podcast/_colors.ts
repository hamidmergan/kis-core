/** One badge colour per speaker, so every list marks the same person the same way. */
const TINTS = ["blue", "amber", "emerald", "rose"] as const;

export interface SpeakerColor {
  bg: string;
  fg: string;
}

export function speakerColor(index: number): SpeakerColor {
  const tint = TINTS[((index % TINTS.length) + TINTS.length) % TINTS.length];
  return { bg: `var(--badge-${tint}-bg)`, fg: `var(--badge-${tint}-fg)` };
}
