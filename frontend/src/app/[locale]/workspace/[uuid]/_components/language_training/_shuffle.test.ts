import { describe, it, expect } from "vitest";
import { shuffleOptions } from "./_shuffle";

describe("shuffleOptions", () => {
  it("leaves a true/false item in its fixed order", () => {
    // Otherwise 'false, true' would appear, and that reads like a bug.
    const item = { options: ["Richtig", "Falsch"], correct_idx: 1 };
    for (let i = 0; i < 20; i++) {
      expect(shuffleOptions(item)).toEqual({ options: ["Richtig", "Falsch"], correct_idx: 1 });
    }
  });

  it("keeps the marked answer on the same text when it shuffles", () => {
    for (let i = 0; i < 20; i++) {
      const out = shuffleOptions({ options: ["a", "b", "c", "d"], correct_idx: 2 });
      expect(out.options[out.correct_idx]).toBe("c");
      expect([...out.options].sort()).toEqual(["a", "b", "c", "d"]);
    }
  });

  it("does change the order of a four-option item", () => {
    const runs = Array.from({ length: 40 }, () =>
      shuffleOptions({ options: ["a", "b", "c", "d"], correct_idx: 0 }).options.join(""));
    expect(new Set(runs).size).toBeGreaterThan(1);
  });

  it("passes an item without options through untouched", () => {
    const item: { front: string; back: string; options?: string[] } = {
      front: "Was ist ein Server?", back: "Ein Rechner",
    };
    expect(shuffleOptions(item)).toBe(item);
  });

  it("passes an item without a marked answer through untouched", () => {
    const item = { options: ["a", "b", "c"] };
    expect(shuffleOptions(item)).toBe(item);
  });
});
