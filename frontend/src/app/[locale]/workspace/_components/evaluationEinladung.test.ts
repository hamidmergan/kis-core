import { describe, it, expect } from "vitest";
import { zeigtEinladung, merkerFuerRunde } from "./evaluationEinladung";

describe("Einladung zur Evaluation", () => {
  it("bleibt weg, solange keine Evaluation laeuft", () => {
    expect(zeigtEinladung({ active: false }, null)).toBe(false);
  });

  it("bleibt weg, wenn schon geantwortet wurde", () => {
    expect(zeigtEinladung({ active: true, already_responded: true, reveal_round: 2 }, null)).toBe(false);
  });

  it("erscheint, wenn nichts weggeklickt wurde", () => {
    expect(zeigtEinladung({ active: true, reveal_round: 0 }, null)).toBe(true);
  });

  it("bleibt weg in derselben Runde, in der sie weggeklickt wurde", () => {
    expect(zeigtEinladung({ active: true, reveal_round: 2 }, "2")).toBe(false);
  });

  it("kommt in der naechsten Runde wieder", () => {
    expect(zeigtEinladung({ active: true, reveal_round: 3 }, "2")).toBe(true);
  });

  it("holt auch die zurueck, die vor dem Rundenzaehler weggeklickt haben", () => {
    expect(zeigtEinladung({ active: true, reveal_round: 1 }, "true")).toBe(true);
  });

  it("laesst den alten Merker in Runde null in Ruhe", () => {
    expect(zeigtEinladung({ active: true, reveal_round: 0 }, "true")).toBe(false);
  });

  it("bleibt weg, wenn gar keine Daten kamen", () => {
    expect(zeigtEinladung(null, null)).toBe(false);
  });

  it("merkt sich die Runde, in der weggeklickt wurde", () => {
    expect(merkerFuerRunde({ active: true, reveal_round: 4 })).toBe("4");
  });
});
