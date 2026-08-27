import { describe, it, expect } from "vitest";
import { setProgressPct } from "./_progress";

describe("setProgressPct", () => {
  it("takes the value the backend already counted", () => {
    // 4 of 5 cards are learned, exactly the reported bug: the ring showed 40.
    expect(setProgressPct({ progress_pct: 80 })).toBe(80);
  });

  it("shows nothing for a set that was never answered", () => {
    expect(setProgressPct({})).toBe(0);
    expect(setProgressPct({ progress_pct: 0 })).toBe(0);
  });

  it("keeps the ring inside the circle", () => {
    // A value above 100 would overdraw the circle, one below 0 would mirror it.
    expect(setProgressPct({ progress_pct: 120 })).toBe(100);
    expect(setProgressPct({ progress_pct: -5 })).toBe(0);
  });

  it("rounds to whole percent", () => {
    expect(setProgressPct({ progress_pct: 66.6 })).toBe(67);
  });

  it("ignores a broken value instead of printing NaN", () => {
    expect(setProgressPct({ progress_pct: Number.NaN })).toBe(0);
  });
});
