import { describe, expect, it } from "vitest";
import {
  GRAMMAR_FORMATS,
  formatChoiceReady,
  sentKinds,
  toggleFormat,
} from "./_grammarFormats";

describe("sentKinds", () => {
  it("sends nothing when all four are ticked", () => {
    // Alle vier IST gemischt, und gemischt wird als NULL gespeichert. Es gibt
    // genau einen Weg, das auszudruecken, naemlich gar nichts zu senden.
    expect(sentKinds([...GRAMMAR_FORMATS])).toBeUndefined();
  });

  it("sends a real choice", () => {
    expect(sentKinds(["transform", "cloze"])).toEqual(["transform", "cloze"]);
  });

  it("sends nothing when nothing is ticked", () => {
    // Der Knopf ist dann ohnehin gesperrt, aber die Funktion darf keinen
    // unmoeglichen Zustand nach hinten geben.
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
    // Wenn der Nutzer "choice" klickt, dann "transform" (umgekehrte Reihenfolge),
    // muss das Ergebnis Katalogordnung haben, nicht Klickordnung.
    // Das unterscheidet toggleFormat (filter ueber Katalog) von einer naiven
    // append/remove-Implementierung, die ["choice","transform"] ergeben wuerde.
    const afterChoice = toggleFormat([], "choice");
    const afterTransform = toggleFormat(afterChoice, "transform");
    expect(afterTransform).toEqual(["transform", "choice"]);
  });
});
