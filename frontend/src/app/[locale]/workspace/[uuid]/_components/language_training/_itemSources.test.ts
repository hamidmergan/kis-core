import { describe, it, expect } from "vitest";
import { itemSources } from "./_itemSources";

describe("itemSources", () => {
  it("returns nothing for an exercise without a source", () => {
    expect(itemSources({})).toEqual([]);
  });

  it("falls back to the single source on the exercise", () => {
    expect(itemSources({ source_label: "a.pdf", page_number: 3 })).toEqual([
      { source_label: "a.pdf", page_number: 3, start_time: undefined },
    ]);
  });

  it("prefers the source list over the single source", () => {
    const sources = [{ source_label: "b.pdf", page_number: 1 }];
    expect(itemSources({ source_label: "a.pdf", page_number: 3, sources })).toEqual(sources);
  });

  it("drops a place that is cited twice", () => {
    const sources = [
      { source_label: "a.pdf", page_number: 2 },
      { source_label: "a.pdf", page_number: 2 },
      { source_label: "a.pdf", page_number: 4 },
    ];
    expect(itemSources({ sources })).toEqual([sources[0], sources[2]]);
  });

  it("keeps two passages of the same page apart", () => {
    const sources = [
      { source_label: "a.pdf", page_number: 2, highlight_text: "one" },
      { source_label: "a.pdf", page_number: 2, highlight_text: "two" },
    ];
    expect(itemSources({ sources })).toHaveLength(2);
  });
});
