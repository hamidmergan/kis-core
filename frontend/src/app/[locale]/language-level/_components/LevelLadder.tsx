"use client";

import { CEFR_LEVELS, isReached, type CefrLevel } from "@/lib/cefr";

/** The six steps in a row, filled up to the own level. */
export function LevelLadder({ own }: { own: CefrLevel }) {
  return (
    <div
      className="grid w-full"
      style={{ maxWidth: 560, gridTemplateColumns: "repeat(6, minmax(0, 1fr))", gap: 8 }}
    >
      {CEFR_LEVELS.map((step) => {
        const reached = isReached(step, own);
        return (
          <div key={step} className="flex flex-col items-center gap-2.5">
            <div
              className="h-2 w-full rounded"
              style={{ backgroundColor: reached ? "var(--kb)" : "var(--border-soft)" }}
            />
            <span
              className="text-sm"
              style={{ color: reached ? "var(--kb)" : "var(--muted-soft)", fontWeight: step === own ? 600 : 500 }}
            >
              {step}
            </span>
          </div>
        );
      })}
    </div>
  );
}
