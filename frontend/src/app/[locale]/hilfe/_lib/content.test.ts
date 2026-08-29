import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { readHelpTree, readHelpArticle } from "./articles";

/** Guards the real content, not the fixtures. Addresses are flat, so slugs must be unique. */
describe("Der echte Hilfe-Inhalt", () => {
  const tree = readHelpTree("de");

  it("hat Gruppen mit Artikeln", () => {
    expect(tree.length).toBeGreaterThan(0);
    for (const group of tree) expect(group.articles.length).toBeGreaterThan(0);
  });

  it("vergibt jede Adresse nur einmal", () => {
    const slugs = tree.flatMap((g) => g.articles.map((a) => a.slug));
    expect(slugs).toEqual([...new Set(slugs)]);
  });

  it("gibt jeder Gruppe einen Namen aus _titel.txt", () => {
    for (const group of tree) expect(group.title).not.toBe(group.key);
  });

  it("hat zu jedem deutschen Artikel einen englischen", () => {
    const en = readHelpTree("en");
    expect(en.flatMap((g) => g.articles.map((a) => a.slug))).toEqual(
      tree.flatMap((g) => g.articles.map((a) => a.slug)),
    );
    for (const group of en) {
      for (const article of group.articles) expect(article.title).not.toBe(article.slug);
    }
  });

  it("zeigt auf Bilder, die es wirklich gibt", () => {
    for (const locale of ["de", "en"]) {
      for (const group of readHelpTree(locale)) {
        for (const article of group.articles) {
          const body = readHelpArticle(locale, article.slug)!.body.replaceAll("{lang}", locale);
          for (const match of body.matchAll(/!\[[^\]]*\]\((\/[^)\s]+)\)/g)) {
            const file = path.join(process.cwd(), "public", match[1]);
            expect(fs.existsSync(file), `${locale}/${article.slug}: ${match[1]}`).toBe(true);
          }
        }
      }
    }
  });
});
