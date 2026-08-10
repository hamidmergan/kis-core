import { describe, it, expect } from "vitest";
import { checkGap, normalizeAnswer } from "./_cloze";

describe("normalizeAnswer", () => {
  it("wirft Ränder, Grossschreibung und Satzzeichen weg", () => {
    expect(normalizeAnswer("  Arbeitet.  ")).toBe("arbeitet");
    expect(normalizeAnswer("Filter,")).toBe("filter");
  });

  it("wirft Klammereinschübe weg, wie der Vergleich im Backend", () => {
    expect(normalizeAnswer("gewechselt (Perfekt)")).toBe("gewechselt");
  });

  it("macht aus nichts nichts", () => {
    expect(normalizeAnswer("")).toBe("");
    expect(normalizeAnswer("   ")).toBe("");
  });
});

describe("checkGap", () => {
  it("nimmt die genaue Lösung an", () => {
    expect(checkGap("arbeitet", "arbeitet")).toBe("correct");
  });

  it("stört sich nicht an Gross- und Kleinschreibung oder einem Punkt", () => {
    expect(checkGap("Arbeitet.", "arbeitet")).toBe("correct");
  });

  it("nennt die falsche Endung fast richtig", () => {
    // Der Lernende hat das richtige Wort und die falsche Form. Genau darum geht
    // die Übung, also darf das nicht dasselbe Urteil sein wie ein falsches Wort.
    expect(checkGap("arbeiten", "arbeitet")).toBe("close");
    expect(checkGap("wechselt", "gewechselt")).toBe("close");
  });

  it("nennt einen Buchstabendreher fast richtig", () => {
    expect(checkGap("gewechselt", "gewechselt")).toBe("correct");
    expect(checkGap("gewechseelt", "gewechselt")).toBe("close");
  });

  it("nennt ein anderes Wort falsch", () => {
    expect(checkGap("messen", "läuft")).toBe("wrong");
    expect(checkGap("hat", "hut")).toBe("wrong");
  });

  it("nennt eine leere Eingabe falsch", () => {
    expect(checkGap("", "arbeitet")).toBe("wrong");
    expect(checkGap("   ", "arbeitet")).toBe("wrong");
  });
});
