import { describe, expect, it } from "vitest";
import { filterTree } from "./filterTree";
import type { DokuGroup } from "./articles";

const TREE: DokuGroup[] = [
  {
    key: "erste-schritte",
    title: "Erste Schritte",
    adminOnly: false,
    articles: [
      { slug: "anmelden", title: "Anmelden" },
      { slug: "oberflaeche", title: "Die Oberflaeche" },
    ],
  },
  {
    key: "verwaltung",
    title: "Fuer Verwaltende",
    adminOnly: true,
    articles: [{ slug: "nutzer", title: "Nutzer und Rechte" }],
  },
];

describe("filterTree", () => {
  it("blendet die Verwaltungs-Gruppe ohne Adminrecht aus", () => {
    expect(filterTree(TREE, "", false).map((g) => g.key)).toEqual(["erste-schritte"]);
  });

  it("zeigt sie mit Adminrecht", () => {
    expect(filterTree(TREE, "", true).map((g) => g.key)).toEqual(["erste-schritte", "verwaltung"]);
  });

  it("filtert Artikel nach dem Titel, ohne Ruecksicht auf Gross und Klein", () => {
    const result = filterTree(TREE, "ANMELD", true);
    expect(result).toHaveLength(1);
    expect(result[0].articles.map((a) => a.slug)).toEqual(["anmelden"]);
  });

  it("behaelt eine Gruppe ganz, wenn der Gruppenname passt", () => {
    const result = filterTree(TREE, "erste", true);
    expect(result[0].articles).toHaveLength(2);
  });

  it("liefert eine leere Liste, wenn nichts passt", () => {
    expect(filterTree(TREE, "zzz", true)).toEqual([]);
  });

  it("findet auch bei einem Treffer in der Verwaltungs-Gruppe nichts ohne Adminrecht", () => {
    expect(filterTree(TREE, "nutzer", false)).toEqual([]);
  });
});
