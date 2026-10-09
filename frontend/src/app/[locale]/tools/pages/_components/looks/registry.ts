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
  /** Looks of one family read alike, such as a table and two columns of points; two never follow each other. */
  family?: "grid" | "boxes";
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
  apart(page, looks, out);
  return out;
}

/**
 * Two blocks that read alike never follow each other, even with running text between them:
 * the later one takes a look of another family, else the earlier one does.
 */
function apart(page: Page, looks: Looks, out: Map<string, number>): void {
  const seq: { at: string; b: Block }[] = [];
  page.sections.forEach((s, i) => s.blocks.forEach((b, j) => {
    if (s.id !== "cover" && !s.hidden && b.kind !== "text" && out.has(`${i}.${j}`)) seq.push({ at: `${i}.${j}`, b });
  }));
  const all = (b: Block) => (looks[b.kind] as Look[] | undefined) ?? [];
  const family = (x: { at: string; b: Block }) => all(x.b)[out.get(x.at) ?? 0]?.family;
  const other = (x: { at: string; b: Block }, avoid: (string | undefined)[]) => {
    const used = new Set(seq.filter((y) => y.at !== x.at && y.b.kind === x.b.kind).map((y) => out.get(y.at)));
    const ok = all(x.b).map((l, k) => ({ l, k }))
      .filter(({ l }) => (l.fits?.(x.b as never) ?? true) && !avoid.includes(l.family));
    return (ok.find(({ k }) => !used.has(k)) ?? ok[0])?.k;
  };
  for (let n = 1; n < seq.length; n++) {
    const f = family(seq[n]);
    if (!f || f !== family(seq[n - 1])) continue;
    const later = other(seq[n], [f]);
    if (later != null) { out.set(seq[n].at, later); continue; }
    const earlier = other(seq[n - 1], [f, n > 1 ? family(seq[n - 2]) : undefined]);
    if (earlier != null) out.set(seq[n - 1].at, earlier);
  }
}
