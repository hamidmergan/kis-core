import { describe, it, expect } from "vitest";
import { hatAnfang } from "./intro";

describe("Anfang der Evaluation", () => {
  it("faellt weg, wenn Text und Link fehlen", () => {
    expect(hatAnfang({})).toBe(false);
  });

  it("faellt weg, wenn nur Leerzeichen im Text stehen", () => {
    expect(hatAnfang({ intro_text: "   " })).toBe(false);
  });

  it("bleibt stehen, sobald ein Text da ist", () => {
    expect(hatAnfang({ intro_text: "Willkommen" })).toBe(true);
  });

  it("bleibt stehen, wenn nur ein Link da ist", () => {
    expect(hatAnfang({ intro_link_url: "https://th-luebeck.de" })).toBe(true);
  });

  it("faellt weg, wenn gar keine Daten kamen", () => {
    expect(hatAnfang(null)).toBe(false);
  });
});
