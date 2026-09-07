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
  it("bekommen die Stationen zum Hochladen und Freigeben gar nicht erst", () => {
    // Ohne Lehrenden-Vorschau gibt es weder Plus noch Freigabe-Zeichen, beide Stationen zeigten ins Leere.
    expect(schluessel(false)).not.toContain("hochladen");
    expect(schluessel(false)).not.toContain("freigeben");
    expect(demoSchritte(false)).toHaveLength(DEMO_SCHRITTE.length - 2);
  });

  it("bekommen für Begrüßung, Materialbereich, Hinweis, Statistik und Schluss eigene Texte", () => {
    const keys = schluessel(false);
    expect(keys).toContain("willkommenStudi");
    expect(keys).toContain("materialienStudi");
    expect(keys).toContain("hinweisStudi");
    expect(keys).toContain("statistikStudi");
    expect(keys).toContain("schlussStudi");
    expect(keys).not.toContain("willkommen");
    expect(keys).not.toContain("materialien");
    expect(keys).not.toContain("hinweis");
    expect(keys).not.toContain("statistik");
    expect(keys).not.toContain("schluss");
  });

  it("sehen beim Hinweis dasselbe Info-Zeichen, das den Hinweis nur öffnet", () => {
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

  it("Lehrende zeigen beim Hinweis auf dasselbe Info-Zeichen", () => {
    const gefragt = seiteMitschreiben();
    demoSchritte(true).find((s) => s.key === "hinweis")?.ziel?.();
    expect(gefragt).toEqual(['[data-tour="staff-note"]']);
  });
});

describe("Die Statistik im Studio", () => {
  it("spricht Lehrende und Studierende getrennt an", () => {
    // Beide sehen dort nur die eigenen Zahlen, gesagt werden muss es der lehrenden Seite.
    expect(schluessel(true)).toContain("statistik");
    expect(schluessel(false)).toContain("statistikStudi");
  });
});

describe("Der Hinweis oben rechts", () => {
  it("steht bei beiden Fassungen direkt hinter der Begrüßung", () => {
    // Das Info-Zeichen sitzt in der Kopfleiste, mitten in der Materialliste
    // sprang der Rundgang dafür nach oben rechts und gleich wieder zurück.
    expect(schluessel(true)[1]).toBe("hinweis");
    expect(schluessel(false)[1]).toBe("hinweisStudi");
  });
});

describe("Zurück auf dem Smartphone", () => {
  it("jede Station mit Ziel holt ihren Bereich selbst nach vorn", () => {
    // Auf dem Telefon bleiben alle drei Bereiche gebaut und werden nur
    // unsichtbar geschaltet, das Ziel steht also auch im verdeckten Bereich
    // noch auf der Seite. Ohne eigenes Vorbereiten zeigt der Rundgang beim
    // Zurückgehen auf eine unsichtbare Stelle im falschen Bereich.
    // Ausgenommen sind Ziele in der Kopfleiste, die kein Bereich je verdeckt.
    const ohneVorbereitung = [...demoSchritte(true), ...demoSchritte(false)]
      .filter((s) => s.ziel && !s.vorbereiten && !s.imKopf)
      .map((s) => s.key);
    expect(ohneVorbereitung).toEqual([]);
  });
});
