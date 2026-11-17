import { describe, it, expect } from "vitest";
import { selectedCharCount, selectionHasText } from "./_pdfSelection";

const stateWith = (slices?: Record<string, { count?: number }>) => ({
  state: { plugins: { selection: { documents: { doc1: { slices } } } } },
  documentId: "doc1",
});

describe("selectionHasText", () => {
  it("is true when a page holds selected characters", () => {
    expect(selectionHasText(stateWith({ "0": { count: 0 }, "1": { count: 12 } }))).toBe(true);
  });

  it("is false when every page counts zero", () => {
    expect(selectionHasText(stateWith({ "0": { count: 0 }, "1": {} }))).toBe(false);
  });

  it("is false for an empty selection", () => {
    expect(selectionHasText(stateWith({}))).toBe(false);
  });

  it("stays true while the state is not known yet", () => {
    expect(selectionHasText(stateWith(undefined))).toBe(true);
    expect(selectionHasText({ state: undefined, documentId: "doc1" })).toBe(true);
    expect(selectionHasText({ state: { plugins: {} }, documentId: "other" })).toBe(true);
  });
});

describe("selectedCharCount", () => {
  it("sums the pages and tells unknown apart from empty", () => {
    expect(selectedCharCount(stateWith({ "0": { count: 3 }, "1": { count: 12 } }))).toBe(15);
    expect(selectedCharCount(stateWith({}))).toBe(0);
    expect(selectedCharCount(stateWith(undefined))).toBeNull();
  });
});
