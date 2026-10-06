import { describe, it, expect } from "vitest";
import { zuSenden } from "./antworten";

const FRAGEN = [
  { id: "a", type: "choice" as const, text: "Wie einfach?" },
  { id: "b", type: "text" as const, text: "Was fehlt?" },
  { id: "c", type: "multi" as const, text: "Welche Tools?" },
];

describe("Antworten zum Abschicken", () => {
  it("laesst nichts uebrig, wenn niemand etwas beantwortet hat", () => {
    expect(zuSenden(FRAGEN, {})).toEqual([]);
  });

  it("wirft einen Text aus lauter Leerzeichen weg", () => {
    expect(zuSenden(FRAGEN, { b: "   " })).toEqual([]);
  });

  it("wirft eine leere Mehrfachauswahl weg", () => {
    expect(zuSenden(FRAGEN, { c: [] })).toEqual([]);
  });

  it("nimmt nur die beantworteten Fragen mit", () => {
    expect(zuSenden(FRAGEN, { a: "Leicht" })).toEqual([{ question_id: "a", value: "Leicht" }]);
  });

  it("nimmt eine Mehrfachauswahl mit", () => {
    expect(zuSenden(FRAGEN, { c: ["Quiz", "Mindmap"] })).toEqual([
      { question_id: "c", value: ["Quiz", "Mindmap"] },
    ]);
  });

  it("behaelt die Reihenfolge der Fragen", () => {
    expect(zuSenden(FRAGEN, { b: "Nichts", a: "Schwer" })).toEqual([
      { question_id: "a", value: "Schwer" },
      { question_id: "b", value: "Nichts" },
    ]);
  });

  it("laesst eine versteckte Frage weg, auch wenn sie eine Antwort hat", () => {
    const fragen = [
      { id: "a", type: "choice" as const, text: "Bereich?" },
      { id: "b", type: "text" as const, text: "Nur bei A", show_if: { question_id: "a", in: ["A"] } },
    ];
    expect(zuSenden(fragen, { a: "B", b: "Trotzdem beantwortet" })).toEqual([
      { question_id: "a", value: "B" },
    ]);
  });
});
