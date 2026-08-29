import { describe, expect, it } from "vitest";
import { fileURLToPath } from "node:url";
import { readDokuTree, readDokuArticle, firstSlug } from "./articles";

const ROOT = fileURLToPath(new URL("./__fixtures__", import.meta.url));

describe("readDokuTree", () => {
  it("sortiert Gruppen und Artikel nach der Zahl vorn", () => {
    const tree = readDokuTree("de", ROOT);
    expect(tree.map((g) => g.key)).toEqual(["erste-schritte", "verwaltung"]);
    expect(tree[0].articles.map((a) => a.slug)).toEqual(["anmelden", "oberflaeche"]);
  });

  it("nimmt den Gruppennamen aus _titel.txt", () => {
    const tree = readDokuTree("de", ROOT);
    expect(tree[0].title).toBe("Erste Schritte");
  });

  it("nimmt den Artikeltitel aus der ersten Ueberschrift", () => {
    const tree = readDokuTree("de", ROOT);
    expect(tree[0].articles[0].title).toBe("Anmelden");
  });

  it("markiert eine Gruppe mit der Endung -admin", () => {
    const tree = readDokuTree("de", ROOT);
    expect(tree[0].adminOnly).toBe(false);
    expect(tree[1].adminOnly).toBe(true);
  });

  it("baut das englische Menue aus der deutschen Struktur", () => {
    const tree = readDokuTree("en", ROOT);
    expect(tree.map((g) => g.key)).toEqual(["erste-schritte", "verwaltung"]);
    expect(tree[0].articles.map((a) => a.slug)).toEqual(["anmelden", "oberflaeche"]);
  });

  it("nimmt den englischen Titel wenn es die Datei gibt", () => {
    const tree = readDokuTree("en", ROOT);
    expect(tree[0].articles[0].title).toBe("Signing in");
  });

  it("faellt fuer fehlende englische Dateien auf Deutsch zurueck", () => {
    const tree = readDokuTree("en", ROOT);
    expect(tree[0].articles[1].title).toBe("Die Oberflaeche");
    expect(tree[0].title).toBe("Erste Schritte");
  });
});

describe("readDokuArticle", () => {
  it("liefert Titel und Text", () => {
    const article = readDokuArticle("de", "anmelden", ROOT);
    expect(article?.title).toBe("Anmelden");
    expect(article?.body).toContain("Text auf Deutsch.");
  });

  it("faellt auf die deutsche Datei zurueck", () => {
    const article = readDokuArticle("en", "oberflaeche", ROOT);
    expect(article?.body).toContain("Noch ein Text.");
  });

  it("liefert null fuer eine unbekannte Adresse", () => {
    expect(readDokuArticle("de", "gibtsnicht", ROOT)).toBeNull();
  });
});

describe("firstSlug", () => {
  it("liefert den ersten Artikel der ersten Gruppe", () => {
    expect(firstSlug(readDokuTree("de", ROOT))).toBe("anmelden");
  });

  it("liefert null bei leerem Baum", () => {
    expect(firstSlug([])).toBeNull();
  });
});
