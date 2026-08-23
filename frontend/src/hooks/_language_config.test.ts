import { describe, expect, it } from "vitest";

import { pickAllowed } from "./_language_config";

const ALLE = [
  { id: "DE", label: "Deutsch" },
  { id: "EN-US", label: "Englisch" },
  { id: "FR", label: "Franzoesisch" },
  { id: "TR", label: "Tuerkisch" },
];

describe("pickAllowed", () => {
  it("laesst ohne Einschraenkung alles durch", () => {
    expect(pickAllowed(ALLE, undefined, "TR")).toEqual({ languages: ALLE, target: "TR" });
  });

  it("behaelt nur die erlaubten Sprachen", () => {
    const { languages } = pickAllowed(ALLE, ["DE", "EN-US"], "EN-US");
    expect(languages.map((l) => l.id)).toEqual(["DE", "EN-US"]);
  });

  it("holt eine nicht erlaubte Zielsprache zurueck", () => {
    // Die Stimme spricht kein Tuerkisch, also darf es auch nicht eingestellt bleiben.
    expect(pickAllowed(ALLE, ["DE", "EN-US"], "TR").target).toBe("DE");
  });

  it("laesst eine erlaubte Zielsprache stehen", () => {
    expect(pickAllowed(ALLE, ["DE", "EN-US"], "EN-US").target).toBe("EN-US");
  });

  it("faellt nicht um, wenn nichts uebrig bleibt", () => {
    const { languages, target } = pickAllowed(ALLE, ["XX"], "TR");
    expect(languages).toEqual([]);
    expect(target).toBe("TR");
  });
});
