import { describe, expect, it } from "vitest";
import {
  GRAMMAR_FORMATS,
  formatChoiceReady,
  sentKinds,
  toggleFormat,
} from "./_grammarFormats";

describe("sentKinds", () => {
  it("sends nothing when mixed is picked", () => {
    // Gemischt ist der Normalfall und wird als NULL gespeichert. Es gibt genau
    // einen Weg, das auszudruecken, naemlich gar nichts zu senden.
    expect(sentKinds(false, ["transform"])).toBeUndefined();
  });

  it("sends nothing when all four are ticked", () => {
    // Alle vier IST gemischt.
    expect(sentKinds(true, [...GRAMMAR_FORMATS])).toBeUndefined();
  });

  it("sends a real choice", () => {
    expect(sentKinds(true, ["transform", "cloze"])).toEqual(["transform", "cloze"]);
  });

  it("sends nothing when nothing is ticked", () => {
    // Der Knopf ist dann ohnehin gesperrt, aber die Funktion darf keinen
    // unmoeglichen Zustand nach hinten geben.
    expect(sentKinds(true, [])).toBeUndefined();
  });

  it("keeps the catalogue order, not the clicking order", () => {
    expect(sentKinds(true, ["choice", "transform"])).toEqual(["transform", "choice"]);
  });
});

describe("formatChoiceReady", () => {
  it("is ready when mixed is picked", () => {
    expect(formatChoiceReady(false, [])).toBe(true);
  });

  it("is not ready with no format ticked", () => {
    expect(formatChoiceReady(true, [])).toBe(false);
  });

  it("is ready with one format ticked", () => {
    expect(formatChoiceReady(true, ["cloze"])).toBe(true);
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
});
