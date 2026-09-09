import { describe, it, expect } from "vitest";
import { zuSenden } from "./antworten";

const FRAGEN = [
  { id: "a", type: "scale" as const, text: "Wie einfach?" },
  { id: "b", type: "text" as const, text: "Was fehlt?" },
];

describe("Antworten zum Abschicken", () => {
  it("laesst nichts uebrig, wenn niemand etwas beantwortet hat", () => {
    expect(zuSenden(FRAGEN, {})).toEqual([]);
  });

  it("wirft einen Text aus lauter Leerzeichen weg", () => {
    expect(zuSenden(FRAGEN, { b: "   " })).toEqual([]);
  });

  it("nimmt nur die beantworteten Fragen mit", () => {
    expect(zuSenden(FRAGEN, { a: 4 })).toEqual([{ question_id: "a", value: 4 }]);
  });

  it("behaelt die Reihenfolge der Fragen", () => {
    expect(zuSenden(FRAGEN, { b: "Nichts", a: 2 })).toEqual([
      { question_id: "a", value: 2 },
      { question_id: "b", value: "Nichts" },
    ]);
  });
});
