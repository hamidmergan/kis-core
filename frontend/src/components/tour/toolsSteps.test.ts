import { describe, it, expect } from "vitest";
import { werkzeugRundgang } from "./toolsSteps";
import { TOOL_ROUTES, type ToolKey } from "@/lib/modules";

const ALLE = TOOL_ROUTES.map((t) => t.key);
const schluessel = (sichtbar: readonly ToolKey[]) => werkzeugRundgang(sichtbar).map((s) => s.key);

describe("Wer alle Werkzeuge sieht", () => {
  it("bekommt die Leiste, jedes Werkzeug und die Aufträge", () => {
    expect(schluessel(ALLE)).toEqual([
      "seitenleiste",
      "translation",
      "tts",
      "transcription",
      "image",
      "summary",
      "screencast",
      "glossary",
      "auftraege",
      "abschluss",
    ]);
  });
});

describe("Wer nur einzelne Werkzeuge freigeschaltet hat", () => {
  it("bekommt genau deren Stationen, der Rahmen bleibt stehen", () => {
    expect(schluessel(["tts", "glossary"])).toEqual([
      "seitenleiste",
      "tts",
      "glossary",
      "auftraege",
      "abschluss",
    ]);
  });

  it("läuft in der Reihenfolge der Leiste, nicht in der übergebenen", () => {
    // Die Seitenleiste ordnet nach TOOL_ROUTES, ein Rundgang in anderer
    // Reihenfolge sprang in der Liste hoch und runter.
    expect(schluessel(["glossary", "translation"])).toEqual([
      "seitenleiste",
      "translation",
      "glossary",
      "auftraege",
      "abschluss",
    ]);
  });
});

describe("Wer gar kein Werkzeug hat", () => {
  it("bekommt keinen Rundgang, denn die Leiste steht dann auch nicht da", () => {
    expect(werkzeugRundgang([])).toEqual([]);
  });
});

describe("Aufbau der Stationen", () => {
  it("jede Werkzeug-Station öffnet die Adresse aus der Leiste", () => {
    for (const { key, href } of TOOL_ROUTES) {
      expect(werkzeugRundgang(ALLE).find((s) => s.key === key)?.route).toBe(href);
    }
  });

  it("Leiste und Aufträge öffnen nichts, sie zeigen auf die Stelle, wo man steht", () => {
    const rahmen = werkzeugRundgang(ALLE).filter((s) => s.key === "seitenleiste" || s.key === "auftraege");
    expect(rahmen.map((s) => s.route)).toEqual([undefined, undefined]);
  });

  it("jede Station zeigt auf einen Anker, nie auf eine CSS-Klasse", () => {
    for (const s of werkzeugRundgang(ALLE)) {
      expect(s.anker).toMatch(/^[a-z-]+$/);
    }
  });
});

describe("Der Anker einer Werkzeug-Station", () => {
  it("gehoert genau einem Werkzeug", () => {
    // Beim Sprung steht die alte Seite noch einen Moment auf der Seite. Mit
    // einem gemeinsamen Anker für alle Werkzeuge zeigte der Rundgang dann auf
    // das Feld, das gerade verschwindet.
    const anker = werkzeugRundgang(ALLE).map((s) => s.anker);
    expect(new Set(anker).size).toBe(anker.length);
  });

  it("traegt den Schluessel des Werkzeugs", () => {
    expect(werkzeugRundgang(ALLE).find((s) => s.key === "screencast")?.anker).toBe("tool-screencast");
  });
});

describe("Der Abschluss", () => {
  it("steht am Ende und zeigt auf nichts", () => {
    const schritte = werkzeugRundgang(ALLE);
    expect(schritte.at(-1)?.key).toBe("abschluss");
    expect(schritte.at(-1)?.ohneZiel).toBe(true);
  });
});
