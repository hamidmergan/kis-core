import { describe, expect, it } from "vitest";

import { indexToStep, istErreichbar, vorherErreichbar } from "./steps";

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

describe("istErreichbar", () => {
  it("laesst nur betretbare Seiten zu", () => {
    expect(istErreichbar(0, ALLE_ERREICHT, false, "done")).toBe(false);
    expect(istErreichbar(1, ALLE_ERREICHT, false, "done")).toBe(false);
    expect(istErreichbar(3, ALLE_ERREICHT, false, "done")).toBe(true);
  });

  // Rendern ist eine Warteseite, bis das Video steht. Danach liegt dort der
  // Rueckblick mit allen Folien zum Nachhoeren.
  it("gibt Rendern erst frei, wenn das Video fertig ist", () => {
    expect(istErreichbar(6, ALLE_ERREICHT, false, "done")).toBe(true);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "tts-settings")).toBe(false);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "script-review")).toBe(false);
  });

  it("sperrt, was noch nicht dran war", () => {
    expect(istErreichbar(5, 3, false, "user-prompt")).toBe(false);
    expect(istErreichbar(2, 3, false, "user-prompt")).toBe(true);
  });

  it("sperrt Pruefen, wenn die Uebersetzung uebersprungen wurde", () => {
    expect(istErreichbar(2, ALLE_ERREICHT, true, "user-prompt")).toBe(false);
    expect(istErreichbar(2, ALLE_ERREICHT, false, "user-prompt")).toBe(true);
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

  it("im Rueckblick sind die Schritte 2 bis 5 wieder erreichbar", () => {
    expect(istErreichbar(2, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
    expect(istErreichbar(3, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
    expect(istErreichbar(4, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
    expect(istErreichbar(5, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
  });

  it("im Rueckblick ist auch Schritt 6 selbst erreichbar", () => {
    expect(istErreichbar(6, ALLE_ERREICHT, false, "rendering", true)).toBe(true);
  });

  it("generating-scripts sperrt immer, auch im Rueckblick", () => {
    expect(istErreichbar(2, ALLE_ERREICHT, false, "generating-scripts", true)).toBe(false);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "generating-scripts", true)).toBe(false);
  });

  it("auf done aendert der Rueckblick-Schalter nichts, Schritt 6 bleibt erreichbar", () => {
    expect(istErreichbar(6, ALLE_ERREICHT, false, "done")).toBe(true);
    expect(istErreichbar(6, ALLE_ERREICHT, false, "done", true)).toBe(true);
  });

  it("maxReachedIdx begrenzt weiterhin, auch im Rueckblick", () => {
    expect(istErreichbar(5, 3, false, "rendering", true)).toBe(false);
  });

  it("skipTranslation blendet die Uebersetzung weiterhin aus, auch im Rueckblick", () => {
    expect(istErreichbar(1, ALLE_ERREICHT, true, "rendering", true)).toBe(false);
    expect(istErreichbar(2, ALLE_ERREICHT, true, "rendering", true)).toBe(false);
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

  it("ueberspringt die uebersprungene Uebersetzung", () => {
    expect(vorherErreichbar(3, ALLE_ERREICHT, true, "user-prompt")).toBeNull();
    expect(vorherErreichbar(4, ALLE_ERREICHT, true, "script-review")).toBe(3);
  });

  it("gibt nichts auf der Upload-Seite", () => {
    expect(vorherErreichbar(0, 0, false, "upload")).toBeNull();
  });

  it("findet im Rueckblick den naechsten Schritt nach links, waehrend des Laufs nichts", () => {
    expect(vorherErreichbar(6, ALLE_ERREICHT, false, "rendering", true)).toBe(5);
    expect(vorherErreichbar(6, ALLE_ERREICHT, false, "rendering", false)).toBeNull();
  });
});
