"use client";

import type { ReactNode } from "react";
import { Txt } from "../Txt";
import type { Look, LookProps } from "./registry";
import { PlainCaption, vars } from "./shared";

type ScaleBlock = LookProps<"scale">["b"];
const clamp01 = (v: number) => Math.min(1, Math.max(0, Number.isFinite(v) ? v : 0));
const sortedItems = (b: ScaleBlock) => b.items.map((it, i) => ({ ...it, pos: clamp01(it.pos), i })).sort((u, v) => u.pos - v.pos);
/** The smallest distance between items that share a side, every k-th neighbour. */
const minGap = (b: ScaleBlock, k: number) => {
  const s = sortedItems(b);
  return Math.min(1, ...s.slice(k).map((it, i) => it.pos - s[i].pos));
};
const shortLabels = (b: ScaleBlock) => b.items.every((it) => it.label.length <= 24);
const edge = (pos: number) => (pos < 0.15 ? " v-nu-sc-el" : pos > 0.85 ? " v-nu-sc-er" : "");

function ScaleFig({ b, p, limits, cls, children }: LookProps<"scale"> & { cls: string; children: ReactNode }) {
  return (
    <figure className="v-nu-root">
      <div className={cls} style={vars({ "--nh": `${Math.max(280, b.items.length * 60)}px` })}>
        <Txt path={`${p}.left`} value={b.left} className="v-nu-sc-pole" max={limits.short} />
        {children}
        <Txt path={`${p}.right`} value={b.right} className="v-nu-sc-pole" max={limits.short} />
      </div>
      <PlainCaption p={p} b={b} limits={limits} />
    </figure>
  );
}

function ScLine(x: LookProps<"scale">) {
  const { b, p, limits } = x;
  return (
    <ScaleFig {...x} cls="v-nu-sc-line">
      <div className="v-nu-sc-rail">
        {sortedItems(b).map((it) => (
          <i key={it.i} className={`v-nu-sc-pt${edge(it.pos)}`} style={vars({ "--p": it.pos })} data-d={`${p}.items.${it.i}`}>
            <Txt path={`${p}.items.${it.i}.label`} value={it.label} max={limits.short} />
          </i>
        ))}
      </div>
    </ScaleFig>
  );
}

function ScBand(x: LookProps<"scale">) {
  const { b, p, limits } = x;
  const s = sortedItems(b), n = s.length;
  // A section reaches from the middle before its item to the middle after it.
  const bounds = [0, ...s.slice(0, -1).map((it, i) => (it.pos + s[i + 1].pos) / 2), 1];
  return (
    <ScaleFig {...x} cls="v-nu-sc-band">
      <div className="v-nu-sc-bsegs">
        {s.map((it, i) => (
          <div key={it.i} className="v-nu-sc-bseg" data-d={`${p}.items.${it.i}`}
            style={vars({ "--w": (bounds[i + 1] - bounds[i]).toFixed(3), "--m": `${Math.round(25 + (75 * i) / Math.max(1, n - 1))}%` })}>
            <i />
            <Txt path={`${p}.items.${it.i}.label`} value={it.label} max={limits.short} />
          </div>
        ))}
      </div>
    </ScaleFig>
  );
}

function ScAlt(x: LookProps<"scale">) {
  const { b, p, limits } = x;
  return (
    <ScaleFig {...x} cls="v-nu-sc-alt">
      <div className="v-nu-sc-track">
        {sortedItems(b).map((it, k) => (
          <i key={it.i} className={`v-nu-sc-kn ${k % 2 ? "v-nu-sc-dn" : "v-nu-sc-up"}`} style={vars({ "--p": it.pos })} data-d={`${p}.items.${it.i}`}>
            <i />
            <Txt path={`${p}.items.${it.i}.label`} value={it.label} max={limits.short} />
          </i>
        ))}
      </div>
    </ScaleFig>
  );
}

export const SCALE: Look<"scale">[] = [
  { name: "Linie zwischen Polen", fits: (b) => b.items.length <= 6 && shortLabels(b) && minGap(b, 1) >= 0.14, View: ScLine },
  { name: "Abschnittsband", View: ScBand },
  { name: "Regler-Punkte", fits: (b) => b.items.length <= 8 && shortLabels(b) && minGap(b, 2) >= 0.14, View: ScAlt },
];
