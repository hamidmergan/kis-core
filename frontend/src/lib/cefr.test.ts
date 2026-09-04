import { describe, expect, it } from "vitest";
import { CEFR_LEVELS, isReached } from "./cefr";

describe("CEFR_LEVELS", () => {
  it("walks the ladder from A1 to C2", () => {
    expect(CEFR_LEVELS).toEqual(["A1", "A2", "B1", "B2", "C1", "C2"]);
  });
});

describe("isReached", () => {
  it("counts every step up to and including the own level", () => {
    expect(isReached("A1", "B1")).toBe(true);
    expect(isReached("B1", "B1")).toBe(true);
  });

  it("leaves the steps above the own level open", () => {
    expect(isReached("B2", "B1")).toBe(false);
    expect(isReached("C2", "A1")).toBe(false);
  });
});
