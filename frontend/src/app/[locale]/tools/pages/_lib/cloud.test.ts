import { describe, expect, it } from "vitest";
import { sizedWords } from "./cloud";

describe("sizedWords", () => {
  it("keeps the sizes of a list that is already sorted", () => {
    expect(sizedWords([["a", 9], ["b", 5], ["c", 1]])).toEqual([
      { word: "a", size: 66 },
      { word: "b", size: 16 + Math.sqrt(0.5) * 50 },
      { word: "c", size: 16 },
    ]);
  });

  it("sorts weights edited out of order, so no size turns into NaN", () => {
    const out = sizedWords([["a", 5], ["b", 1], ["c", 3]]);
    expect(out.map((w) => w.word)).toEqual(["a", "c", "b"]);
    expect(out.every((w) => Number.isFinite(w.size))).toBe(true);
    expect(out[2].size).toBe(16);
  });

  it("gives equal weights the smallest size and an empty list nothing", () => {
    expect(sizedWords([["a", 2], ["b", 2]]).map((w) => w.size)).toEqual([16, 16]);
    expect(sizedWords([])).toEqual([]);
  });
});
