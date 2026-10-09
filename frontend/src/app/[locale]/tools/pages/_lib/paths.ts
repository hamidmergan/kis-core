import type { Block, Page } from "./types";

/** Every text and item on the page carries its place in page.json as a dotted path. */

type Node = Record<string, unknown> | unknown[];

export function getAt(page: Page, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o == null ? o : (o as Record<string, unknown>)[k]), page);
}

export function setAt(page: Page, path: string, value: unknown): void {
  const keys = path.split(".");
  const last = keys.pop()!;
  const parent = keys.reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], page) as Node;
  (parent as Record<string, unknown>)[last] = value;
}

/** Removes an item from its list, a single field is emptied instead. */
export function deleteAt(page: Page, path: string): void {
  const keys = path.split(".");
  const last = keys.pop()!;
  const parent = keys.reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], page) as Node;
  if (Array.isArray(parent)) parent.splice(Number(last), 1);
  else (parent as Record<string, unknown>)[last] = "";
}

const LISTS = ["items", "cards", "steps", "figures", "bars", "rows", "branches", "words", "events", "pairs"] as const;
const EMPTY: Block = { kind: "empty" };

/** A block with nothing left to read: its last item went, or its only text was cleared. */
function isBare(b: Block): boolean {
  if (b.kind === "empty") return true;
  const rec = b as unknown as Record<string, unknown>;
  if (LISTS.some((k) => Array.isArray(rec[k]) && (rec[k] as unknown[]).length === 0)) return true;
  if (b.kind === "text") return !b.text;
  if (b.kind === "highlight") return !b.key && !b.text;
  if (b.kind === "quote") return !b.text;
  if (b.kind === "formula") return !b.key;
  if (b.kind === "versus" || b.kind === "venn") return !b.a.items.length && !b.b.items.length;
  return false;
}

/**
 * A bare block is removed, an empty shell helps no reader. In an added section it turns back
 * into an empty field, so the grid keeps its places.
 */
export function dropEmptyBlocks(page: Page): void {
  for (const s of page.sections) {
    s.blocks = s.layout
      ? s.blocks.map((b) => (b.kind !== "empty" && isBare(b) ? { ...EMPTY } : b))
      : s.blocks.filter((b) => !isBare(b));
  }
}

/** Removes what the bin points at, a whole field of an added section becomes empty again. */
export function removeAt(page: Page, path: string): void {
  const m = /^sections\.(\d+)\.blocks\.(\d+)$/.exec(path);
  const s = m ? page.sections[Number(m[1])] : null;
  if (m && s?.layout) s.blocks[Number(m[2])] = { ...EMPTY };
  else deleteAt(page, path);
  dropEmptyBlocks(page);
}

/** Every picture name on the page, to count them against the limit. */
export const imageCount = (page: Page) =>
  page.sections.reduce((n, s) => n + s.blocks.filter((b) => b.kind === "image").length, 0);

export const clone = <T,>(o: T): T => JSON.parse(JSON.stringify(o));
