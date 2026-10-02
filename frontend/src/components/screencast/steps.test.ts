import { describe, expect, it } from "vitest";

import { indexToStep, istErreichbar, nieBetretbar, vorherErreichbar } from "./steps";

const ALLE_ERREICHT = 7;

describe("indexToStep", () => {
  it("kennt die Seiten, die man wieder betreten darf", () => {
    expect(indexToStep(2)).toBe("translation-review");
    expect(indexToStep(3)).toBe("user-prompt");
    expect(indexToStep(4)).toBe("script-review");
    expect(indexToStep(5)).toBe("tts-settings");
    expect(indexToStep(6)).toBe("rendering");
    expect(indexToStep(7)).toBe("done");
  });

  it("gibt nichts fuer Upload und Uebersetzen", () => {
    expect(indexToStep(0)).toBeNull();
    expect(indexToStep(1)).toBeNull();
  });
});

describe("nieBetretbar", () => {
  it("meldet Upload und Uebersetzen als fuer immer zu", () => {
    expect(nieBetretbar(0, false)).toBe(true);
    expect(nieBetretbar(1, false)).toBe(true);
  });

  it("meldet Pruefen trotz uebersprungener Uebersetzung nicht als fuer immer zu", () => {
    expect(nieBetretbar(2, true)).toBe(false);
    expect(nieBetretbar(2, false)).toBe(false);
  });

  it("meldet nur gerade gesperrte Seiten nicht als tot", () => {
    expect(nieBetretbar(6, false)).toBe(false);
    expect(nieBetretbar(7, false)).toBe(false);
  });
});

describe("istErreichbar", () => {
  it("laesst nur betretbare Seiten zu", () => {
    expect(istErreichbar(0, ALLE_ERREICHT, false, "done")).toBe(false);
    expect(istErreichbar(1, ALLE_ERREICHT, false, "done")).toBe(false);
    expect(istErreichbar(3, ALLE_ERREICHT, false, "done")).toBe(true);
  });

  // Rendering is a waiting page, afterwards the review sits there.
  it("gibt Rendern erst frei, wenn das Video fertig ist", () => {
    expect(istErreichbar(6, ALLE_ERREICHT, false, "done")).toBe(true);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "tts-settings")).toBe(false);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "script-review")).toBe(false);
  });

  it("sperrt, was noch nicht dran war", () => {
    expect(istErreichbar(5, 3, false, "user-prompt")).toBe(false);
    expect(istErreichbar(2, 3, false, "user-prompt")).toBe(true);
  });

  it("laesst Pruefen zu, auch wenn die Uebersetzung uebersprungen wurde", () => {
    expect(istErreichbar(2, ALLE_ERREICHT, true, "user-prompt")).toBe(true);
    expect(istErreichbar(2, ALLE_ERREICHT, false, "user-prompt")).toBe(true);
  });

  it("Index 2 ist erreichbar, wenn die Uebersetzung uebersprungen wurde und maxReachedIdx hoch genug ist", () => {
    expect(istErreichbar(2, 2, true, "user-prompt")).toBe(true);
    expect(istErreichbar(2, 1, true, "user-prompt")).toBe(false);
  });

  it("Index 1 bleibt gesperrt, wenn die Uebersetzung uebersprungen wurde", () => {
    expect(istErreichbar(1, ALLE_ERREICHT, true, "user-prompt")).toBe(false);
  });

  it("sperrt alles, solange etwas laeuft", () => {
    expect(istErreichbar(3, ALLE_ERREICHT, false, "rendering")).toBe(false);
    expect(istErreichbar(3, ALLE_ERREICHT, false, "generating-scripts")).toBe(false);
  });

  it("waehrend des Laufs ist kein Schritt erreichbar", () => {
    expect(istErreichbar(2, ALLE_ERREICHT, false, "rendering")).toBe(false);
    expect(istErreichbar(4, ALLE_ERREICHT, false, "rendering")).toBe(false);
    expect(istErreichbar(5, ALLE_ERREICHT, false, "rendering")).toBe(false);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "rendering")).toBe(false);
  });

  it("mit fertigem Video sind die Schritte 2 bis 5 wieder erreichbar", () => {
    expect(istErreichbar(2, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
    expect(istErreichbar(3, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
    expect(istErreichbar(4, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
    expect(istErreichbar(5, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
  });

  it("mit fertigem Video ist auch Schritt 6 selbst erreichbar", () => {
    expect(istErreichbar(6, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
  });

  it("generating-scripts sperrt immer, auch mit fertigem Video", () => {
    expect(istErreichbar(2, ALLE_ERREICHT, false, "generating-scripts", true)).toBe(false);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "generating-scripts", true)).toBe(false);
  });

  it("auf done aendert hatErgebnis nichts, Schritt 6 bleibt erreichbar", () => {
    expect(istErreichbar(6, ALLE_ERREICHT, false, "done")).toBe(true);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "done", true)).toBe(true);
  });

  it("maxReachedIdx begrenzt weiterhin, auch mit fertigem Video", () => {
    expect(istErreichbar(5, 3, false, "rendering", true)).toBe(false);
  });

  it("skipTranslation blendet nur die Uebersetzung aus, Pruefen bleibt frei, auch mit fertigem Video", () => {
    expect(istErreichbar(1, ALLE_ERREICHT, true, "rendering", true)).toBe(false);
    expect(istErreichbar(2, ALLE_ERREICHT, true, "rendering", true)).toBe(true);
  });

  it("von Schritt 5 aus ist Schritt 6 erreichbar, wenn ein Video fertig ist", () => {
    expect(istErreichbar(6, ALLE_ERREICHT, false, "script-review", true)).toBe(true);
  });

  it("ohne fertiges Video ist Schritt 6 von Schritt 5 aus nicht erreichbar", () => {
    expect(istErreichbar(6, ALLE_ERREICHT, false, "script-review", false)).toBe(false);
  });
});

describe("vorherErreichbar", () => {
  it("gibt die Seite davor", () => {
    expect(vorherErreichbar(5, ALLE_ERREICHT, false, "tts-settings")).toBe(4);
    expect(vorherErreichbar(4, ALLE_ERREICHT, false, "script-review")).toBe(3);
  });

  it("ueberspringt Warteseiten und Upload", () => {
    expect(vorherErreichbar(3, ALLE_ERREICHT, false, "user-prompt")).toBe(2);
    expect(vorherErreichbar(2, ALLE_ERREICHT, false, "translation-review")).toBeNull();
  });

  it("ueberspringt nur noch das uebersprungene Uebersetzen, Pruefen bleibt Ziel", () => {
    expect(vorherErreichbar(3, ALLE_ERREICHT, true, "user-prompt")).toBe(2);
    expect(vorherErreichbar(2, ALLE_ERREICHT, true, "translation-review")).toBeNull();
    expect(vorherErreichbar(4, ALLE_ERREICHT, true, "script-review")).toBe(3);
  });

  it("gibt nichts auf der Upload-Seite", () => {
    expect(vorherErreichbar(0, 0, false, "upload")).toBeNull();
  });

  it("findet mit fertigem Video den naechsten Schritt nach links, waehrend des Laufs ohne Video nichts", () => {
    expect(vorherErreichbar(6, ALLE_ERREICHT, false, "rendering", true)).toBe(5);
    expect(vorherErreichbar(6, ALLE_ERREICHT, false, "rendering", false)).toBeNull();
  });
});

