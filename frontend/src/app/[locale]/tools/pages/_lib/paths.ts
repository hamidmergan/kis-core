import type { Page } from "./types";

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

const LISTS = ["items", "cards", "steps", "figures", "bars", "rows", "branches", "words"] as const;

/** A block whose last item went is removed with it, an empty shell helps no reader. */
export function dropEmptyBlocks(page: Page): void {
  for (const s of page.sections) {
    s.blocks = s.blocks.filter((b) => {
      const rec = b as unknown as Record<string, unknown>;
      return !LISTS.some((k) => Array.isArray(rec[k]) && (rec[k] as unknown[]).length === 0);
    });
  }
}

export const clone = <T,>(o: T): T => JSON.parse(JSON.stringify(o));
