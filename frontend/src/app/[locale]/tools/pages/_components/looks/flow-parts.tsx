"use client";

import type { Entry as EntryData, Limits } from "../../_lib/types";
import { useNumber } from "../Charts";
import { Txt } from "../Txt";

/** A point on a circle, the angle in degrees clockwise from the top. */
export function pt(cx: number, cy: number, r: number, deg: number): [number, number] {
  const a = ((deg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}
export const f1 = (n: number) => n.toFixed(1);
export const pc = (n: number, of: number) => `${((n / of) * 100).toFixed(2)}%`;

export function Arrow() {
  return <svg className="v-fl-arr" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h16M13 6l6 6-6 6" /></svg>;
}

export function Dot({ n }: { n: number }) {
  const fmt = useNumber();
  return <span className="v-fl-dot">{fmt(n)}</span>;
}

/** The title and the text of one entry at p. */
export function Entry({ p, e, limits }: { p: string; e: EntryData; limits: Limits }) {
  return (
    <>
      <Txt path={`${p}.title`} value={e.title} as="h3" max={limits.short} />
      <Txt path={`${p}.text`} value={e.text} as="p" max={limits.item} />
    </>
  );
}
