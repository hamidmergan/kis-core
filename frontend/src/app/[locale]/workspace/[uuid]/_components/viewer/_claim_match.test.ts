import { describe, it, expect } from "vitest";
import { normalizePageText, extractNumbers, findClaimSpot, segmentUnits } from "./_claim_match";

const PAGE = [
  "Kapitel 3 Finanzierung",
  "Die Hochschule verfügt über ein jährliches Budget von 25.000 Euro für",
  "internationale Projekte. Davon entfallen rund 40 Prozent auf Reisekosten.",
  "Die restlichen Mittel werden für Sprachkurse verwendet.",
  "",
  "Kapitel 4 Organisation",
  "Das International Office koordiniert alle Partnerschaften mit Hochschulen",
  "im Ausland und berät Studierende bei der Bewerbung.",
].join("\r\n");

function slice(text: string, spans: { start: number; end: number }[]): string[] {
  return spans.map((s) => text.slice(s.start, s.end));
}

describe("normalizePageText", () => {
  it("collapses whitespace but keeps one newline per line break", () => {
    const { text, toRaw } = normalizePageText("a  b\r\n\r\nc\td");
    expect(text).toBe("a b\nc d");
    expect(toRaw[text.indexOf("c")]).toBe("a  b\r\n\r\nc".length - 1);
  });
});

describe("extractNumbers", () => {
  it("reads German thousands, decimals and k/Mio suffixes", () => {
    expect(extractNumbers("25.000 Euro").map((n) => n.value)).toEqual([25000]);
    expect(extractNumbers("25k Euro").map((n) => n.value)).toEqual([25000]);
    expect(extractNumbers("1.234,56 Euro").map((n) => n.value)).toEqual([1234.56]);
    expect(extractNumbers("3.14").map((n) => n.value)).toEqual([3.14]);
    expect(extractNumbers("2,5 Mio. Euro").map((n) => n.value)).toEqual([2_500_000]);
    expect(extractNumbers("im Jahr 2024").map((n) => n.value)).toEqual([2024]);
  });

  it("reads German and English number words", () => {
    expect(extractNumbers("fünfundzwanzigtausend Euro").map((n) => n.value)).toEqual([25000]);
    expect(extractNumbers("zweihundertfünfzig Plätze").map((n) => n.value)).toEqual([250]);
    expect(extractNumbers("twenty-five thousand euros").map((n) => n.value)).toEqual([25000]);
    expect(extractNumbers("two hundred and fifty seats").map((n) => n.value)).toEqual([250]);
    expect(extractNumbers("drei Millionen").map((n) => n.value)).toEqual([3_000_000]);
  });

  it("does not turn articles into numbers", () => {
    expect(extractNumbers("eine Hochschule und ein Büro")).toEqual([]);
  });
});

describe("segmentUnits", () => {
  it("splits prose at sentence ends and slides at short lines", () => {
    const { text } = normalizePageText(PAGE);
    const units = slice(text, segmentUnits(text));
    expect(units).toContain("Kapitel 3 Finanzierung");
    expect(units.some((u) => u.startsWith("Die Hochschule verfügt") && u.endsWith("Projekte."))).toBe(true);
    expect(units).toContain("Davon entfallen rund 40 Prozent auf Reisekosten.");
  });
});

describe("segmentUnits on a slide", () => {
  const SLIDE = [
    "• Indirektes Zitat",
    "• sinngemäße, nicht wortwörtliche Wiedergabe",
    "• Keine Anführungszeichen setzen",
    "• „vgl.“ vor dem Namen der Autor:innen",
    "ZITATARTEN 1/2",
    "WISSENSCHAFTLICHES SCHREIBEN UND ZITIEREN",
    "15.04.2026",
  ].join("\r\n");

  it("keeps every bullet and every heading line on its own", () => {
    const { text } = normalizePageText(SLIDE);
    const units = slice(text, segmentUnits(text));
    expect(units).toContain("• Keine Anführungszeichen setzen");
    expect(units).toContain("ZITATARTEN 1/2");
    expect(units).toContain("WISSENSCHAFTLICHES SCHREIBEN UND ZITIEREN");
  });

  it("bridges one bullet without claim words when the next carries some", () => {
    const { text } = normalizePageText([
      "• Wörtliches/direktes Zitat", "• Originalzitat", "• In Anführungszeichen setzen",
      "• Buchstabengetreue Übernahme (auch wenn Fehler enthalten sind)", "• Seitenzahl angeben",
      "• Indirektes Zitat", "• sinngemäße, nicht wortwörtliche Wiedergabe", "• Keine Anführungszeichen setzen",
      "• „vgl.“ vor dem Namen der Autor:innen", "ZITATARTEN 1/2",
    ].join("\r\n"));
    const hit = findClaimSpot(text, "Wörtliche Zitate stehen in Anführungszeichen und müssen buchstabengetreu übernommen werden. Indirekte Zitate sind sinngemäße Wiedergaben ohne Anführungszeichen und werden mit dem Kürzel vgl. eingeleitet.");
    const got = slice(text, hit!.spans).join(" ");
    expect(got).toContain("Wörtliches/direktes Zitat");
    expect(got).toContain("Keine Anführungszeichen setzen");
    expect(got).not.toContain("ZITATARTEN");
  });

  it("marks the bullets of the claim, not the slide title", () => {
    const { text } = normalizePageText(SLIDE);
    const hit = findClaimSpot(text, "Indirekte Zitate sind sinngemäße Wiedergaben ohne Anführungszeichen und werden mit vgl. eingeleitet.");
    expect(hit?.kind).toBe("passage");
    const got = slice(text, hit!.spans).join(" ");
    expect(got).toContain("Indirektes Zitat");
    expect(got).toContain("Anführungszeichen");
    expect(got).not.toContain("ZITATARTEN");
  });
});

describe("findClaimSpot", () => {
  it("finds the sentence that carries the claim, across a line break", () => {
    const { text } = normalizePageText(PAGE);
    const hit = findClaimSpot(text, "Für internationale Projekte stehen jährlich 25k Euro bereit.");
    expect(hit?.kind).toBe("passage");
    const got = slice(text, hit!.spans).join(" ");
    expect(got).toContain("Budget von 25.000 Euro");
    expect(got).toContain("internationale Projekte.");
  });

  it("matches a number written out in words", () => {
    const { text } = normalizePageText(PAGE);
    const hit = findClaimSpot(text, "Das Budget beträgt fünfundzwanzigtausend Euro.");
    expect(hit?.kind).toBe("passage");
    expect(slice(text, hit!.spans).join(" ")).toContain("25.000 Euro");
  });

  it("grows to the neighbouring sentence when the claim spans both", () => {
    const { text } = normalizePageText(PAGE);
    const hit = findClaimSpot(text, "Vom Budget gehen 40 Prozent an Reisekosten, der Rest an Sprachkurse.");
    expect(hit?.kind).toBe("passage");
    const got = slice(text, hit!.spans).join(" ");
    expect(got).toContain("40 Prozent");
    expect(got).toContain("Sprachkurse");
    expect(got).not.toContain("International Office");
  });

  it("falls back to keywords when no sentence stands out", () => {
    const { text } = normalizePageText(PAGE);
    const hit = findClaimSpot(text, "Ausland Mittel");
    expect(hit?.kind).toBe("keywords");
    expect(slice(text, hit!.spans)).toEqual(["Ausland"]);
  });

  it("marks the whole sentence for a single verbatim keyword", () => {
    const { text } = normalizePageText(PAGE);
    const hit = findClaimSpot(text, "Partnerschaften");
    expect(hit?.kind).toBe("passage");
    expect(slice(text, hit!.spans).join(" ")).toContain("International Office koordiniert");
  });

  it("ignores a word that only echoes the file name in the footer", () => {
    const { text } = normalizePageText("ORGANISATORISCHES\r\n25.03.2026\r\nWissenschaftliches Seminar - Einführung - Lenka Kleinau, M.Sc.\r\n6");
    expect(findClaimSpot(text, "Webkonferenz (Einführung)", "01_Einführung_WissenschaftlichesSeminar2.pdf")).toBeNull();
    expect(findClaimSpot(text, "Webkonferenz (Einführung)")?.kind).toBe("passage");
  });

  it("returns null when nothing of the claim is on the page", () => {
    const { text } = normalizePageText(PAGE);
    expect(findClaimSpot(text, "Quantenmechanik Schrödinger Wellenfunktion")).toBeNull();
  });

  it("tolerates hyphenation at a line break", () => {
    const { text } = normalizePageText("Die Ver-\r\nwaltung prüft jeden Antrag sorgfältig auf Vollständigkeit.\r\nEin zweiter Satz ohne Bezug steht hier.");
    const hit = findClaimSpot(text, "Die Verwaltung prüft Anträge auf Vollständigkeit.");
    expect(hit?.kind).toBe("passage");
    expect(slice(text, hit!.spans).join(" ")).toContain("Vollständigkeit");
  });
});
