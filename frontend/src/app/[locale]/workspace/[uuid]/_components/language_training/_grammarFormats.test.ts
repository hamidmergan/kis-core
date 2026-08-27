import { describe, expect, it } from "vitest";
import {
  GRAMMAR_FORMATS,
  formatChoiceReady,
  sentKinds,
  toggleFormat,
} from "./_grammarFormats";

describe("sentKinds", () => {
  it("sends nothing when all four are ticked", () => {
    // All four is mixed and is stored as NULL.
    expect(sentKinds([...GRAMMAR_FORMATS])).toBeUndefined();
  });

  it("sends a real choice", () => {
    expect(sentKinds(["transform", "cloze"])).toEqual(["transform", "cloze"]);
  });

  it("sends nothing when nothing is ticked", () => {
    // The function must not return an impossible state.
    expect(sentKinds([])).toBeUndefined();
  });

  it("keeps the catalogue order, not the clicking order", () => {
    expect(sentKinds(["choice", "transform"])).toEqual(["transform", "choice"]);
  });
});

describe("formatChoiceReady", () => {
  it("is not ready with no format ticked", () => {
    expect(formatChoiceReady([])).toBe(false);
  });

  it("is ready with one format ticked", () => {
    expect(formatChoiceReady(["cloze"])).toBe(true);
  });

  it("is ready with all four ticked", () => {
    expect(formatChoiceReady([...GRAMMAR_FORMATS])).toBe(true);
  });
});

describe("toggleFormat", () => {
  it("adds a format that was off", () => {
    expect(toggleFormat(["transform"], "cloze")).toEqual(["transform", "cloze"]);
  });

  it("removes a format that was on", () => {
    expect(toggleFormat(["transform", "cloze"], "transform")).toEqual(["cloze"]);
  });

  it("may empty the list, the create button guards that", () => {
    expect(toggleFormat(["cloze"], "cloze")).toEqual([]);
  });

  it("preserves catalogue order when toggled in reverse-catalogue click order", () => {
    // The result is in catalogue order, not click order.
    const afterChoice = toggleFormat([], "choice");
    const afterTransform = toggleFormat(afterChoice, "transform");
    expect(afterTransform).toEqual(["transform", "choice"]);
  });
});
