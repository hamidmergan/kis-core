/** Colours of the three verdicts, shared by the typed grammar answer and the cloze. */
export const VERDICT_STYLE: Record<"correct" | "close" | "wrong", { fg: string; bg: string }> = {
  correct: { fg: "#1a8a5c", bg: "rgba(26,138,92,0.08)" },
  close: { fg: "#b07d1a", bg: "rgba(176,125,26,0.10)" },
  wrong: { fg: "#d4453a", bg: "rgba(212,69,58,0.07)" },
};
