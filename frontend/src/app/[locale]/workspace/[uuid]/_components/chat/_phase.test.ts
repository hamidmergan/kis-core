import { describe, it, expect } from "vitest";
import { phaseAt, GRACE_MS, MIN_MS } from "./_phase";

const base = { elapsedMs: 0, qmapAtMs: null, hasText: false, isPopup: false };

describe("phaseAt", () => {
  it("shows nothing inside the grace period", () => {
    expect(phaseAt({ ...base, elapsedMs: GRACE_MS - 1 })).toBeNull();
  });

  it("shows nothing once the first word has arrived", () => {
    expect(phaseAt({ ...base, elapsedMs: 5000, hasText: true })).toBeNull();
  });

  it("searches while no qmap has arrived", () => {
    expect(phaseAt({ ...base, elapsedMs: 2000 })).toBe("searching");
  });

  it("skips the search line for a selection popup", () => {
    expect(phaseAt({ ...base, elapsedMs: 2000, isPopup: true })).toBe("generating");
  });

  it("keeps the search line readable even when the search was quick", () => {
    const at = { ...base, qmapAtMs: GRACE_MS + 50 };
    expect(phaseAt({ ...at, elapsedMs: GRACE_MS + 60 })).toBe("searching");
    expect(phaseAt({ ...at, elapsedMs: GRACE_MS + MIN_MS - 1 })).toBe("searching");
    expect(phaseAt({ ...at, elapsedMs: GRACE_MS + MIN_MS })).toBe("generating");
  });

  it("never shows a search line that would flash before the grace period", () => {
    expect(phaseAt({ ...base, elapsedMs: GRACE_MS, qmapAtMs: 200 })).toBe("generating");
  });

  it("switches to generating when the search took longer than the minimum", () => {
    const at = { ...base, qmapAtMs: 2000 };
    expect(phaseAt({ ...at, elapsedMs: 1999 })).toBe("searching");
    expect(phaseAt({ ...at, elapsedMs: 2000 })).toBe("generating");
  });
});
