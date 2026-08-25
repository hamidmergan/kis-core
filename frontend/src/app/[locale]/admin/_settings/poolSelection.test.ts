import { describe, expect, it } from "vitest";

import { chosenCount, POOL_TOOLS } from "./poolSelection";

describe("Auswahl in der Vorrats-Karte", () => {
  const counts = { tools: { quiz: 12, grammatik: 5 }, schedule: 4 };

  it("zaehlt nur die angehakten Werkzeuge", () => {
    expect(chosenCount(counts, ["quiz"], false)).toBe(12);
    expect(chosenCount(counts, ["quiz", "grammatik"], false)).toBe(17);
  });

  it("zaehlt den Zeitplan dazu, wenn er angehakt ist", () => {
    expect(chosenCount(counts, ["quiz"], true)).toBe(16);
  });

  it("ist ohne Haken null", () => {
    expect(chosenCount(counts, [], false)).toBe(0);
  });

  it("nimmt ein Werkzeug ohne Vorrat als null, statt NaN zu liefern", () => {
    expect(chosenCount(counts, ["flashcards"], false)).toBe(0);
  });

  it("kennt die fuenf Werkzeuge mit Vorrat", () => {
    expect(POOL_TOOLS).toEqual([
      "flashcards", "karteikarten", "quiz", "grammatik", "wortschatz",
    ]);
  });
});
