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

  it("ersetzt Bindestriche durch Leerzeichen, wie im Backend", () => {
    // Both hyphen spellings have to be equivalent.
    expect(normalizeAnswer("E-Mail")).toBe(normalizeAnswer("E Mail"));
  });

  it("faltet ß zu ss, wie casefold() im Backend", () => {
    // Both spellings of the sharp s have to normalise alike.
    expect(normalizeAnswer("Anschluß")).toBe(normalizeAnswer("anschluss"));
    expect(normalizeAnswer("Straße")).toBe(normalizeAnswer("strasse"));
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
    // The right word in the wrong form is not the same as a wrong word.
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

  it("akzeptiert Bindestriche und Schrägstriche als unwichtig", () => {
    // Hyphens and slashes are typographic variants of the same answer.
    expect(checkGap("E Mail", "E-Mail")).toBe("correct");
    expect(checkGap("und oder", "und/oder")).toBe("correct");
  });

  it("wertet ß und ss in beiden Richtungen als richtig, wie das Backend", () => {
    expect(checkGap("anschluss", "Anschluß")).toBe("correct");
    expect(checkGap("Straße", "strasse")).toBe("correct");
  });
});
