import type { Block, Design, Page, Section } from "../../_lib/types";
import { pickLooks, seedOf, type Looks } from "./registry";
import { LOOKS_COMPARE } from "./compare";
import { LOOKS_FLOW } from "./flow";
import { LOOKS_NUMBERS } from "./numbers";
import { LOOKS_TEXT } from "./text";
import { LOOKS_VISUAL } from "./visual";
import "./sections.css";

export const LOOKS: Looks = { ...LOOKS_TEXT, ...LOOKS_FLOW, ...LOOKS_NUMBERS, ...LOOKS_COMPARE, ...LOOKS_VISUAL };

/** The look of every block of a page, keyed "section.block". */
export const looksOf = (page: Page) => pickLooks(page, LOOKS);

/** How a section of the subject is built around its blocks. */
export type SectionLook = "top" | "left" | "band" | "center" | "number" | "split" | "rail" | "poster" | "pair" | "shout";

// The section builds each design takes turns with, so a page keeps one character.
const POOLS: Record<Design, SectionLook[]> = {
  chapters: ["number", "left", "top", "shout"],
  timeline: ["rail"],
  magazine: ["band", "top", "poster", "center"],
  guide: ["left", "top", "shout"],
};

// Blocks that need the whole width and never stand in half a row.
const WIDE = new Set<Block["kind"]>(["table", "chart", "matrix", "timeline", "tree", "mindmap", "wordcloud", "venn", "image",
  "steps", "cycle", "levels", "scale", "versus", "accordion", "figures", "bars", "cards"]);

const chars = (b: Block) => JSON.stringify(b).length;

/** A section of one short text-like block or two, it may share a row with its neighbour. */
const small = (s: Section) =>
  s.blocks.length > 0 && s.blocks.length <= 2 && s.blocks.every((b) => !WIDE.has(b.kind))
  && s.blocks.reduce((n, b) => n + chars(b), 0) + s.lead.length < 700;

/** One picture beside one short block, the picture takes half the width. */
const splits = (s: Section) => {
  if (s.blocks.length !== 2) return false;
  const other = s.blocks.find((b) => b.kind !== "image");
  return s.blocks.some((b) => b.kind === "image") && !!other && !WIDE.has(other.kind) && chars(other) < 900;
};

/**
 * The build of every section of the subject, keyed by its index. Two small neighbours share
 * one row as a pair, at most twice a page and never while editing, where every section keeps
 * its own buttons; every other section takes the design's next build.
 */
export function sectionLooks(page: Page, design: Design, isContent: (s: Section) => boolean, editing: boolean): Map<number, SectionLook> {
  const pool = POOLS[design] ?? POOLS.chapters;
  const seed = seedOf(page.sections.find((s) => s.hero)?.title ?? "");
  const out = new Map<number, SectionLook>();
  let k = 0, pairs = 0;
  const shown = page.sections.map((s, i) => ({ s, i })).filter(({ s }) => isContent(s) && !s.layout && !s.hidden);
  for (let n = 0; n < shown.length; n++) {
    const { s, i } = shown[n];
    const next = shown[n + 1];
    if (!editing && design !== "timeline" && pairs < 2 && next && next.i === i + 1 && small(s) && small(next.s) && !splits(s)) {
      out.set(i, "pair");
      out.set(next.i, "pair");
      pairs++;
      n++;
      continue;
    }
    out.set(i, splits(s) ? "split" : pool[(seed + k++) % pool.length]);
  }
  return out;
}
