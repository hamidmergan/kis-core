import type { ComponentType } from "react";
import type { Block, BlockKind, Limits, Page } from "../../_lib/types";

/** What every look of a block gets: the block, its path in page.json and the page's limits. */
export interface LookProps<K extends BlockKind = BlockKind> {
  b: Extract<Block, { kind: K }>;
  p: string;
  limits: Limits;
  imageBase: string;
  /** Its figure or table number, absent when it carries none. */
  num?: number;
}

/** One way to draw a kind of block; fits says whether its data suits this way. */
export interface Look<K extends BlockKind = BlockKind> {
  name: string;
  fits?: (b: Extract<Block, { kind: K }>) => boolean;
  View: ComponentType<LookProps<K>>;
}

export type Looks = { [K in BlockKind]?: Look<K>[] };

/** A small stable number from a text, so one page always looks the same. */
export function seedOf(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return Math.abs(h);
}

/**
 * The look of every block of the page, keyed "section.block". Each kind starts at a place set
 * by the page's title and moves on with every use, so no look repeats while another one fits.
 */
export function pickLooks(page: Page, looks: Looks): Map<string, number> {
  const seed = seedOf(page.sections.find((s) => s.hero)?.title || page.sections[0]?.title || "");
  const used = new Map<string, Set<number>>();
  const out = new Map<string, number>();
  page.sections.forEach((s, i) => s.blocks.forEach((b, j) => {
    // The title picture always runs wide, it takes the first look of a picture.
    if (s.id === "cover") return;
    const all = looks[b.kind] as Look[] | undefined;
    if (!all?.length) return;
    const taken = used.get(b.kind) ?? new Set<number>();
    used.set(b.kind, taken);
    const start = (seed + b.kind.length * 7) % all.length;
    const order = all.map((_, k) => (start + k) % all.length);
    const fit = order.filter((k) => all[k].fits?.(b as never) ?? true);
    const pick = fit.find((k) => !taken.has(k)) ?? fit[0] ?? order[0];
    taken.add(pick);
    out.set(`${i}.${j}`, pick);
  }));
  return out;
}
