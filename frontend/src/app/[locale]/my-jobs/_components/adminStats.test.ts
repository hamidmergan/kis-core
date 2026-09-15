import { describe, expect, it } from "vitest";
import { gesamtdauerS, phasenzeilen, wertText } from "./adminStats";

describe("phasenzeilen", () => {
  it("gibt die Phasen in fester Reihenfolge", () => {
    const zeilen = phasenzeilen({
      vertonung: { dauer_s: 3 },
      uebersetzung: { dauer_s: 1 },
      bilder: { dauer_s: 2 },
    });

    expect(zeilen.map((z) => z.phase)).toEqual(["uebersetzung", "bilder", "vertonung"]);
  });

  it("ordnet auch die Podcast-Phasen", () => {
    const zeilen = phasenzeilen({
      montage: { dauer_s: 4 },
      vertonung: { dauer_s: 3 },
      material: { dauer_s: 1 },
      skript: { dauer_s: 2 },
    });

    expect(zeilen.map((z) => z.phase)).toEqual(["material", "skript", "vertonung", "montage"]);
  });

  it("haengt unbekannte Phasen hinten an", () => {
    const zeilen = phasenzeilen({ neu: { dauer_s: 1 }, bilder: { dauer_s: 2 } });

    expect(zeilen.map((z) => z.phase)).toEqual(["bilder", "neu"]);
  });

  it("trennt Dauer und Fehler von den uebrigen Feldern", () => {
    const zeilen = phasenzeilen({ vertonung: { dauer_s: 3.5, fehler: "kaputt", folien: 12 } });

    expect(zeilen[0].dauerS).toBe(3.5);
    expect(zeilen[0].fehler).toBe("kaputt");
    expect(zeilen[0].felder).toEqual([{ schluessel: "folien", wert: 12 }]);
  });

  it("laesst leere Werte weg", () => {
    const zeilen = phasenzeilen({ vertonung: { anbieter: "", modell: null, stimme: "anna" } });

    expect(zeilen[0].felder).toEqual([{ schluessel: "stimme", wert: "anna" }]);
  });

  it("behaelt false als Wert", () => {
    const zeilen = phasenzeilen({ bilder: { vorrat_genutzt: false } });

    expect(zeilen[0].felder).toEqual([{ schluessel: "vorrat_genutzt", wert: false }]);
  });

  it("liefert nichts ohne Zahlen", () => {
    expect(phasenzeilen(undefined)).toEqual([]);
    expect(phasenzeilen({})).toEqual([]);
  });
});

describe("gesamtdauerS", () => {
  it("addiert die Dauer aller Phasen", () => {
    expect(gesamtdauerS({ bilder: { dauer_s: 2 }, vertonung: { dauer_s: 3.5 } })).toBe(5.5);
  });

  it("ist null ohne jede Dauer", () => {
    expect(gesamtdauerS({ bilder: { folien: 3 } })).toBeNull();
    expect(gesamtdauerS(undefined)).toBeNull();
  });
});

describe("wertText", () => {
  const woerter = { ja: "ja", nein: "nein" };

  it("schreibt Wahrheitswerte aus", () => {
    expect(wertText("vorrat_genutzt", true, "de", woerter)).toBe("ja");
    expect(wertText("vorrat_genutzt", false, "de", woerter)).toBe("nein");
  });

  it("rechnet die Videogroesse in Megabyte um", () => {
    expect(wertText("video_bytes", 44_040_192, "de", woerter)).toBe("42,0 MB");
  });

  it("rechnet jede Groesse auf _bytes in Megabyte um", () => {
    expect(wertText("mp3_bytes", 44_040_192, "de", woerter)).toBe("42,0 MB");
  });

  it("gruppiert grosse Zahlen nach Gebietsschema", () => {
    expect(wertText("zeichen", 18432, "de", woerter)).toBe("18.432");
    expect(wertText("zeichen", 18432, "en", woerter)).toBe("18,432");
  });

  it("laesst Text unveraendert", () => {
    expect(wertText("stimme", "anna", "de", woerter)).toBe("anna");
  });
});
