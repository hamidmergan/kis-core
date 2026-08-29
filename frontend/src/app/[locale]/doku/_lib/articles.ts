import fs from "node:fs";
import path from "node:path";

export type DokuArticle = { slug: string; title: string };
export type DokuGroup = { key: string; title: string; adminOnly: boolean; articles: DokuArticle[] };

const DEFAULT_ROOT = path.join(process.cwd(), "src", "content", "doku");
const MASTER_LOCALE = "de";

/** Strips the leading order number and the optional -admin marker. */
function nameParts(entry: string): { order: number; key: string; adminOnly: boolean } {
  const withoutExt = entry.replace(/\.md$/, "");
  const match = withoutExt.match(/^(\d+)-(.*)$/);
  const order = match ? Number(match[1]) : 0;
  const rest = match ? match[2] : withoutExt;
  const adminOnly = rest.endsWith("-admin");
  return { order, key: adminOnly ? rest.slice(0, -"-admin".length) : rest, adminOnly };
}

function readIfPresent(file: string): string | null {
  try {
    return fs.readFileSync(file, "utf8");
  } catch {
    return null;
  }
}

/** Reads a file for the locale and falls back to the German master. */
function readLocalized(root: string, locale: string, relative: string): string | null {
  return readIfPresent(path.join(root, locale, relative)) ?? readIfPresent(path.join(root, MASTER_LOCALE, relative));
}

function titleFromMarkdown(markdown: string, fallback: string): string {
  const line = markdown.split("\n").find((l) => l.startsWith("# "));
  return line ? line.slice(2).trim() : fallback;
}

/** Hidden entries are skipped, macOS drops ._ copies that end in .md too. */
function listDir(dir: string): string[] {
  try {
    return fs.readdirSync(dir).filter((entry) => !entry.startsWith("."));
  } catch {
    return [];
  }
}

export function readDokuTree(locale: string, root: string = DEFAULT_ROOT): DokuGroup[] {
  const masterDir = path.join(root, MASTER_LOCALE);
  const groupDirs = listDir(masterDir)
    .filter((entry) => fs.statSync(path.join(masterDir, entry)).isDirectory())
    .map((entry) => ({ entry, ...nameParts(entry) }))
    .sort((a, b) => a.order - b.order);

  return groupDirs.map(({ entry, key, adminOnly }) => {
    const titleFile = readLocalized(root, locale, path.join(entry, "_titel.txt"));
    const articles = listDir(path.join(masterDir, entry))
      .filter((file) => file.endsWith(".md"))
      .map((file) => ({ file, ...nameParts(file) }))
      .sort((a, b) => a.order - b.order)
      .map(({ file, key: slug }) => {
        const markdown = readLocalized(root, locale, path.join(entry, file)) ?? "";
        return { slug, title: titleFromMarkdown(markdown, slug) };
      });
    return { key, title: titleFile?.trim() || key, adminOnly, articles };
  });
}

export function readDokuArticle(
  locale: string,
  slug: string,
  root: string = DEFAULT_ROOT,
): { title: string; body: string } | null {
  const masterDir = path.join(root, MASTER_LOCALE);
  for (const group of listDir(masterDir)) {
    const file = listDir(path.join(masterDir, group)).find(
      (name) => name.endsWith(".md") && nameParts(name).key === slug,
    );
    if (!file) continue;
    const markdown = readLocalized(root, locale, path.join(group, file));
    if (markdown === null) return null;
    return { title: titleFromMarkdown(markdown, slug), body: markdown };
  }
  return null;
}

export function firstSlug(tree: DokuGroup[]): string | null {
  for (const group of tree) {
    if (group.articles.length > 0) return group.articles[0].slug;
  }
  return null;
}
