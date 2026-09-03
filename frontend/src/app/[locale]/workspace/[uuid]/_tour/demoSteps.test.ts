import { describe, it, expect, afterEach } from "vitest";
import { demoSchritte, DEMO_SCHRITTE } from "./demoSteps";

/** Records what a step asks the page for, the steps do nothing else with it. */
function seiteMitschreiben(): string[] {
  const gefragt: string[] = [];
  (globalThis as unknown as { document: unknown }).document = {
    querySelector: (sel: string) => { gefragt.push(sel); return null; },
    querySelectorAll: () => [],
  };
  return gefragt;
}

afterEach(() => {
  delete (globalThis as unknown as { document?: unknown }).document;
});

const schluessel = (darfAnlegen: boolean) => demoSchritte(darfAnlegen).map((s) => s.key);

describe("Lehrende, die selbst Module anlegen dürfen", () => {
  it("bekommen den vollständigen Rundgang", () => {
    expect(demoSchritte(true)).toHaveLength(DEMO_SCHRITTE.length);
    expect(schluessel(true)).toContain("hochladen");
  });
});

describe("Studierende ohne das Recht Module anzulegen", () => {
  it("bekommen die Station zum Hochladen gar nicht erst", () => {
    // Ohne Lehrenden-Vorschau gibt es das Plus nicht, die Station zeigte ins Leere.
    expect(schluessel(false)).not.toContain("hochladen");
    expect(demoSchritte(false)).toHaveLength(DEMO_SCHRITTE.length - 1);
  });

  it("bekommen für Begrüßung, Materialbereich, Hinweis und Schluss eigene Texte", () => {
    const keys = schluessel(false);
    expect(keys).toContain("willkommenStudi");
    expect(keys).toContain("materialienStudi");
    expect(keys).toContain("hinweisStudi");
    expect(keys).toContain("schlussStudi");
    expect(keys).not.toContain("willkommen");
    expect(keys).not.toContain("materialien");
    expect(keys).not.toContain("hinweis");
    expect(keys).not.toContain("schluss");
  });

  it("sehen beim Hinweis den angepinnten Kasten statt der Pinnnadel", () => {
    const gefragt = seiteMitschreiben();
    demoSchritte(false).find((s) => s.key === "hinweisStudi")?.ziel?.();
    expect(gefragt).toEqual(['[data-tour="staff-note"]']);
  });

  it("behalten den Schluss, nur mit anderem Text", () => {
    expect(schluessel(false).at(-1)).toBe("schlussStudi");
  });
});

describe("Aufbau der Schritte", () => {
  it("die Studierenden-Fassung trägt keine Reste der Umschaltung mehr", () => {
    for (const s of [...demoSchritte(true), ...demoSchritte(false)]) {
      expect(s).not.toHaveProperty("studi");
    }
  });

  it("Lehrende zeigen beim Hinweis weiterhin auf die Pinnnadel", () => {
    const gefragt = seiteMitschreiben();
    demoSchritte(true).find((s) => s.key === "hinweis")?.ziel?.();
    expect(gefragt).toEqual(['[data-tour="add-staff-note"]']);
  });
});
