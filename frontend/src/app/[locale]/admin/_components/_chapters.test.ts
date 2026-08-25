import { describe, expect, it } from "vitest";

import { byChapter } from "./_chapters";

const g = (key: string, chapter?: string) => ({ key, chapter, permissions: [] });

describe("byChapter", () => {
  it("fasst aufeinanderfolgende Gruppen eines Kapitels zusammen", () => {
    const out = byChapter([g("aia", "benutzen"), g("tools", "benutzen")]);

    expect(out).toHaveLength(1);
    expect(out[0].chapter).toBe("benutzen");
    expect(out[0].groups.map((x) => x.key)).toEqual(["aia", "tools"]);
  });

  it("beginnt einen neuen Block, wenn das Kapitel wechselt", () => {
    const out = byChapter([g("aia", "benutzen"), g("set.nutzer", "verwalten")]);

    expect(out.map((b) => b.chapter)).toEqual(["benutzen", "verwalten"]);
  });

  // Der Server ist die Reihenfolge. Kaeme dasselbe Kapitel zweimal, waeren es
  // zwei Bloecke, statt Zeilen aus ihrer Reihenfolge zu reissen.
  it("zieht getrennte Gruppen nicht nachtraeglich zusammen", () => {
    const out = byChapter([g("a", "x"), g("b", "y"), g("c", "x")]);

    expect(out.map((b) => b.chapter)).toEqual(["x", "y", "x"]);
  });

  // Ein alter Server ohne Kapitel darf die Tabelle nicht leer lassen.
  it("kommt ohne Kapitelangabe aus", () => {
    const out = byChapter([g("aia"), g("tools")]);

    expect(out).toHaveLength(1);
    expect(out[0].chapter).toBeUndefined();
    expect(out[0].groups).toHaveLength(2);
  });

  it("haelt eine leere Liste aus", () => {
    expect(byChapter([])).toEqual([]);
  });
});
