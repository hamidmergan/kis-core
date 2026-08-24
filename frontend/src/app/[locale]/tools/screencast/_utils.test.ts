import { describe, expect, it } from "vitest";
import { renderProgress, geaenderteFolien, markeFuerFolie, type VertonterStand } from "./_utils";
import type { JobStatus } from "@/lib/api";
import type { SlideData } from "@/types";

const status = (progress: unknown) => ({ progress } as unknown as JobStatus);

describe("renderProgress", () => {
  it("reicht die fertigen Folien durch", () => {
    expect(renderProgress(status({ step: "tts", current: 2, total: 5, fertig: [0, 3] })))
      .toEqual({ kind: "tts", current: 2, total: 5, fertig: [0, 3] });
  });

  it("ein alter Job ohne Liste liefert eine leere Liste", () => {
    expect(renderProgress(status({ step: "tts", current: 2, total: 5 })))
      .toEqual({ kind: "tts", current: 2, total: 5, fertig: [] });
  });

  it("andere Schritte bleiben unveraendert", () => {
    expect(renderProgress(status({ step: "concat" }))).toEqual({ kind: "concat" });
  });
});

const stand: VertonterStand = {
  scripts: ["Skript eins", "Skript zwei"],
  folientexte: ["Folie eins", "Folie zwei"],
  voice_id: "de-anna",
  provider_id: 2,
  target_lang: "EN-US",
};

describe("markeFuerFolie", () => {
  it("unveraendert ergibt keine Marke", () => {
    expect(markeFuerFolie(stand, 0, "Skript eins", "Folie eins")).toBe(null);
  });

  it("geaendertes Skript ergibt skript", () => {
    expect(markeFuerFolie(stand, 0, "Skript neu", "Folie eins")).toBe("skript");
  });

  it("geaenderter Folientext ergibt folie", () => {
    expect(markeFuerFolie(stand, 0, "Skript eins", "Folie neu")).toBe("folie");
  });

  it("beides geaendert nennt das Skript, das betrifft den Nutzer", () => {
    expect(markeFuerFolie(stand, 0, "Skript neu", "Folie neu")).toBe("skript");
  });

  it("Leerzeichen am Rand sind keine Aenderung", () => {
    expect(markeFuerFolie(stand, 0, "  Skript eins  ", "Folie eins\n")).toBe(null);
  });

  it("ohne Abzug gilt nichts als geaendert", () => {
    expect(markeFuerFolie(null, 0, "irgendwas", "anders")).toBe(null);
  });

  it("eine Folie hinter dem Abzug gilt als geaendert", () => {
    expect(markeFuerFolie(stand, 5, "Skript", "Folie")).toBe("skript");
  });
});

describe("geaenderteFolien", () => {
  const slides = (paare: [string, string][]): SlideData[] =>
    paare.map(([script, extractedText], index) => ({
      index, imageBase64: "", extractedText, script,
    }));

  it("liefert die Nummern der geaenderten Folien", () => {
    const s = slides([["Skript eins", "Folie eins"], ["Skript neu", "Folie zwei"]]);
    expect(geaenderteFolien(stand, s)).toEqual([1]);
  });

  it("ohne Abzug ist die Liste leer", () => {
    const s = slides([["a", "b"]]);
    expect(geaenderteFolien(null, s)).toEqual([]);
  });

  it("eine Folie ohne Skript zaehlt nicht, sie hat nichts zu sprechen", () => {
    const s = slides([["Skript eins", "Folie eins"], ["   ", "Folie neu"]]);
    expect(geaenderteFolien(stand, s)).toEqual([]);
  });
});
