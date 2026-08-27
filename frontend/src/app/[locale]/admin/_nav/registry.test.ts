import { describe, expect, it } from "vitest";
import { PERM } from "@/lib/permissions";
import { SECTIONS, allowedSections, allowedTabs, resolve } from "./registry";

/** Die Reiter einer Unterseite haengen am Recht dieser Seite, nicht am
 *  Bereich: Bereiche mit Unterseiten tragen selbst gar kein Recht. */
describe("Reiter einer Unterseite", () => {
  it("erscheinen fuer jemanden, der die Seite sehen darf", () => {
    const found = resolve(["ki-assistent", "sprachniveau"]);
    expect(found?.page?.tabs).toHaveLength(2);
    const tabs = allowedTabs(found!.page!.tabs, found!.page!.perm, [PERM.aiaLevel]);
    expect(tabs.map((t) => t.slug)).toEqual(["einstufung", "ki-verhalten"]);
  });

  it("bleiben weg, wenn das Recht der Seite fehlt", () => {
    const found = resolve(["ki-assistent", "sprachniveau"]);
    expect(allowedTabs(found!.page!.tabs, found!.page!.perm, [PERM.aiaSources])).toEqual([]);
  });
});

/** Jede Seite ohne eigene Reiter braucht ein Component, sonst rendert die
 *  Route nichts und die Adresse zeigt eine leere Seite. */
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

/** Eine Lehrperson bekommt genau ein Recht und darf davon genau einen Reiter
 *  sehen. Alles andere in der Statistik zeigt die ganze Plattform. */
describe("Statistik einer Lehrperson", () => {
  const dozentin = [PERM.statsOwn];

  it("laesst genau den Bereich Statistik uebrig", () => {
    expect(allowedSections(dozentin).map((s) => s.slug)).toEqual(["statistik"]);
  });

  it("zeigt darin nur Meine Module", () => {
    const statistik = allowedSections(dozentin)[0];
    expect(statistik.tabs?.map((t) => t.slug)).toEqual(["meine-module"]);
  });

  it("stellt Meine Module vor die vier globalen Reiter", () => {
    const alle = SECTIONS.find((s) => s.slug === "statistik");
    expect(alle?.tabs?.map((t) => t.slug)).toEqual([
      "meine-module", "nutzer", "werkzeuge", "ki-assistent", "modelle",
    ]);
  });

  it("laesst niemanden ohne das Recht hinein", () => {
    const statistik = SECTIONS.find((s) => s.slug === "statistik")!;
    const fremde = allowedTabs(statistik.tabs, statistik.perm, [PERM.statsUsers]);
    expect(fremde.map((t) => t.slug)).toEqual(["nutzer"]);
  });
});
