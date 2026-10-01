import { describe, expect, it } from "vitest";
import { demoSchritte } from "./_demo";

describe("demoSchritte", () => {
  it("reads, evaluates each file, plans, then writes each section", () => {
    expect(demoSchritte(2, 2)).toEqual([
      { step: "extract" },
      { step: "map", part: 1, total: 2 },
      { step: "map", part: 2, total: 2 },
      { step: "outline" },
      { step: "section", part: 1, total: 2 },
      { step: "section", part: 2, total: 2 },
    ]);
  });
});
