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

  // The server sets the order, duplicates become two blocks.
  it("zieht getrennte Gruppen nicht nachtraeglich zusammen", () => {
    const out = byChapter([g("a", "x"), g("b", "y"), g("c", "x")]);

    expect(out.map((b) => b.chapter)).toEqual(["x", "y", "x"]);
  });

  // An old server without chapters must not leave the table empty.
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
