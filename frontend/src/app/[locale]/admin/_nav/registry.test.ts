import { describe, expect, it } from "vitest";
import { PERM, STATS_PERMS } from "@/lib/permissions";
import { SECTIONS, allowedSections, allowedTabs, resolve } from "./registry";

/** The tabs hang off their page's permission, not off the area. */
describe("Reiter einer Unterseite", () => {
  it("erscheinen fuer jemanden, der die Seite sehen darf", () => {
    const found = resolve(["ai-assistant", "level"]);
    expect(found?.page?.tabs).toHaveLength(2);
    const tabs = allowedTabs(found!.page!.tabs, found!.page!.perm, [PERM.aiaLevel]);
    expect(tabs.map((t) => t.slug)).toEqual(["assessment", "behaviour"]);
  });

  it("bleiben weg, wenn das Recht der Seite fehlt", () => {
    const found = resolve(["ai-assistant", "level"]);
    expect(allowedTabs(found!.page!.tabs, found!.page!.perm, [PERM.aiaSources])).toEqual([]);
  });
});

/** Every page without tabs of its own needs a component. */
describe("Jeder Eintrag rendert etwas", () => {
  it("hat entweder ein Component oder Reiter", () => {
    const leer: string[] = [];
    for (const section of SECTIONS) {
      for (const page of section.pages ?? []) {
        if (!page.Component && !page.tabs?.length) leer.push(`${section.slug}/${page.slug}`);
      }
      if (!section.pages && !section.Component && !section.tabs?.length) leer.push(section.slug);
    }
    expect(leer).toEqual([]);
  });
});

/** Lehrende lesen ihre Zahlen am Modul selbst, in den Einstellungen bleibt nichts uebrig. */
describe("Statistik einer Lehrperson", () => {
  it("oeffnet ohne Verwaltungsrecht keinen Bereich in den Einstellungen", () => {
    expect(allowedSections([PERM.aiaUse])).toEqual([]);
  });

  it("laesst im Bereich Statistik nur die plattformweiten Reiter stehen", () => {
    const alle = SECTIONS.find((s) => s.slug === "stats");
    expect(alle?.tabs?.map((t) => t.slug)).toEqual([
      "users", "tools", "ai-assistant", "models",
    ]);
  });

  it("laesst niemanden ohne das Recht hinein", () => {
    const statistik = SECTIONS.find((s) => s.slug === "stats")!;
    const fremde = allowedTabs(statistik.tabs, statistik.perm, [PERM.statsUsers]);
    expect(fremde.map((t) => t.slug)).toEqual(["users"]);
  });
});

/** The header names the area after its rights, so the two lists must not drift apart. */
describe("Statistik-Rechte", () => {
  it("sind genau die Reiter des Bereichs Statistik", () => {
    const statistik = SECTIONS.find((s) => s.slug === "stats")!;
    expect([...STATS_PERMS].sort()).toEqual(statistik.tabs!.map((t) => t.perm).sort());
  });
});
