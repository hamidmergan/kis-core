import { describe, it, expect } from "vitest";
import type { Source } from "../../_types";
import { groupState, toggleGroupTargets } from "./_selection";

const fertig = (uuid: string): Source => ({ uuid, filename: `${uuid}.pdf`, status: "ready" });
const laeuft = (uuid: string): Source => ({
  uuid, filename: `${uuid}.pdf`, status: "ready", progress: { stage: "ocr" },
});
const kaputt = (uuid: string): Source => ({ uuid, filename: `${uuid}.pdf`, status: "failed" });

describe("Zustand des Gruppen-Hakens", () => {
  it("ist leer, wenn nichts gewaehlt ist", () => {
    expect(groupState([fertig("a"), fertig("b")], [])).toBe("none");
  });

  it("ist voll, wenn alle Fertigen gewaehlt sind", () => {
    expect(groupState([fertig("a"), fertig("b")], ["a", "b"])).toBe("all");
  });

  it("ist halb, wenn nur ein Teil gewaehlt ist", () => {
    expect(groupState([fertig("a"), fertig("b")], ["a"])).toBe("some");
  });

  it("laesst eine noch laufende Datei die Gruppe nicht auf halb festhalten", () => {
    // Otherwise every group with an indexing file would sit on 'some' forever.
    expect(groupState([fertig("a"), laeuft("b")], ["a"])).toBe("all");
  });

  it("zaehlt eine fehlgeschlagene Datei nicht mit", () => {
    expect(groupState([fertig("a"), kaputt("b")], ["a"])).toBe("all");
  });

  it("ist leer, wenn die Gruppe nur Unfertiges enthaelt", () => {
    expect(groupState([laeuft("a")], [])).toBe("none");
  });

  it("ist leer bei einer leeren Gruppe", () => {
    expect(groupState([], [])).toBe("none");
  });
});

describe("Klick auf den Gruppen-Haken", () => {
  it("waehlt die fehlenden Dateien nach", () => {
    expect(toggleGroupTargets([fertig("a"), fertig("b")], ["a"])).toEqual(["b"]);
  });

  it("waehlt alles ab, wenn schon alles gewaehlt war", () => {
    expect(toggleGroupTargets([fertig("a"), fertig("b")], ["a", "b"])).toEqual(["a", "b"]);
  });

  it("fasst unfertige Dateien nie an", () => {
    expect(toggleGroupTargets([fertig("a"), laeuft("b")], [])).toEqual(["a"]);
  });

  it("macht nichts bei einer Gruppe ohne fertige Datei", () => {
    expect(toggleGroupTargets([laeuft("a")], [])).toEqual([]);
  });
});
