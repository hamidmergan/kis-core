import { describe, it, expect } from "vitest";
import { numberMindmapSources, pageNumberOf, timeLabelSeconds } from "./_sourceRefs";

describe("timeLabelSeconds", () => {
  it("reads minutes and hours", () => {
    expect(timeLabelSeconds("2:05")).toBe(125);
    expect(timeLabelSeconds("1:02:03")).toBe(3723);
  });

  it("returns nothing for a label without a colon", () => {
    expect(timeLabelSeconds("12")).toBeUndefined();
  });
});

describe("pageNumberOf", () => {
  it("takes numbers and numeric strings, everything else is 0", () => {
    expect(pageNumberOf(4)).toBe(4);
    expect(pageNumberOf("7")).toBe(7);
    expect(pageNumberOf(undefined)).toBe(0);
    expect(pageNumberOf("x")).toBe(0);
  });
});

describe("numberMindmapSources", () => {
  const map = {
    topic: "root",
    children: [
      { topic: "a", source_label: "b.pdf" },
      { topic: "b", children: [{ topic: "c", source_label: "c.pdf" }] },
    ],
  };

  it("keeps the picked numbers and marks only cited files as used", () => {
    const { index, used } = numberMindmapSources(map, [
      { number: 1, filename: "a.pdf" },
      { number: 2, filename: "b.pdf" },
      { number: 3, filename: "c.pdf" },
    ]);
    expect(index.get("b.pdf")).toBe(2);
    expect(used.has("a.pdf")).toBe(false);
    expect(used.has("c.pdf")).toBe(true);
  });

  it("numbers by tree order when no picked list exists", () => {
    const { index } = numberMindmapSources(map, undefined);
    expect([...index.entries()]).toEqual([["b.pdf", 1], ["c.pdf", 2]]);
  });

  it("is empty without a map", () => {
    expect(numberMindmapSources(null, undefined).index.size).toBe(0);
  });
});
