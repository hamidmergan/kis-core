"use client";

import { Fragment } from "react";
import type { Side } from "../../_lib/types";
import { Txt } from "../Txt";
import { Ic } from "./compare-parts";
import type { Look, LookProps } from "./registry";
import { Items, usePageWords } from "./shared";

function VsSplit({ b, p, limits }: LookProps<"versus">) {
  const w = usePageWords();
  const side = (s: Side, k: "a" | "b") => (
    <div className="v-vs-split-col">
      <Txt path={`${p}.${k}.title`} value={s.title} as="h3" max={limits.short} />
      <ul><Items p={`${p}.${k}.items`} items={s.items} max={limits.item} /></ul>
    </div>
  );
  return (
    <div className="v-cp v-vs-split">
      <div className="v-vs-split-grid">
        {side(b.a, "a")}
        <div className="v-vs-split-axis"><span>{w.vs}</span></div>
        {side(b.b, "b")}
      </div>
    </div>
  );
}

/** Each side as a light card of its own, a title over its points. */
function VsCards({ b, p, limits }: LookProps<"versus">) {
  const side = (s: Side, k: "a" | "b") => (
    <div className={`v-vs-card${b.tone === "good_bad" ? ` v-vs-card-${k === "a" ? "good" : "bad"}` : ""}`}>
      <Txt path={`${p}.${k}.title`} value={s.title} as="h3" max={limits.short} />
      <ul><Items p={`${p}.${k}.items`} items={s.items} max={limits.item} /></ul>
    </div>
  );
  return (
    <div className="v-cp v-vs-cards">
      {side(b.a, "a")}
      {side(b.b, "b")}
    </div>
  );
}

function VsChecks({ b, p, limits }: LookProps<"versus">) {
  const side = (s: Side, k: "a" | "b") => {
    const good = k === "a";
    return (
      <div className={`v-vs-chk-col v-vs-chk-${good ? "good" : "bad"}`}>
        <Txt path={`${p}.${k}.title`} value={s.title} as="h3" max={limits.short} />
        <ul>
          {s.items.map((t, i) => (
            <li key={i} data-d={`${p}.${k}.items.${i}`}>
              <Ic d={good ? "check" : "cross"} />
              <Txt path={`${p}.${k}.items.${i}`} value={t} max={limits.item} />
            </li>
          ))}
        </ul>
      </div>
    );
  };
  return <div className="v-cp v-vs-chk"><div className="v-vs-chk-grid">{side(b.a, "a")}{side(b.b, "b")}</div></div>;
}

function VsRows({ b, p, limits }: LookProps<"versus">) {
  const n = Math.max(b.a.items.length, b.b.items.length);
  const cell = (s: Side, k: "a" | "b", i: number, cls: string) =>
    i < s.items.length ? (
      <div className={cls} data-d={`${p}.${k}.items.${i}`}>
        <Txt path={`${p}.${k}.items.${i}`} value={s.items[i]} max={limits.item} />
      </div>
    ) : <div className={cls} />;
  return (
    <div className="v-cp v-vs-row">
      <div className="v-vs-row-grid">
        <div className="v-vs-row-l v-vs-row-h"><Txt path={`${p}.a.title`} value={b.a.title} max={limits.short} /></div>
        <div className="v-vs-row-dot v-vs-row-top"><i /></div>
        <div className="v-vs-row-r v-vs-row-h"><Txt path={`${p}.b.title`} value={b.b.title} max={limits.short} /></div>
        {Array.from({ length: n }, (_, i) => (
          <Fragment key={i}>
            {cell(b.a, "a", i, "v-vs-row-l")}
            <div className="v-vs-row-dot"><i /></div>
            {cell(b.b, "b", i, "v-vs-row-r")}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function VsScale({ b, p, limits }: LookProps<"versus">) {
  // Title and list of a side fill one column of the grid, so both titles share a row.
  const col = (s: Side, k: "a" | "b") => (
    <Fragment key={k}>
      <Txt path={`${p}.${k}.title`} value={s.title} as="h3" className={`v-vs-scale-t v-vs-scale-${k === "a" ? "good" : "bad"}`} max={limits.short} />
      <ul><Items p={`${p}.${k}.items`} items={s.items} max={limits.item} /></ul>
    </Fragment>
  );
  return (
    <div className="v-cp v-vs-scale">
      <svg className="v-vs-scale-svg" viewBox="0 0 640 206" aria-hidden="true">
        <line className="v-vs-scale-ln" x1={270} y1={200} x2={370} y2={200} />
        <line className="v-vs-scale-ln" x1={320} y1={200} x2={320} y2={70} />
        <line className="v-vs-scale-ln" x1={70} y1={70} x2={570} y2={70} />
        <circle className="v-vs-scale-pivot" cx={320} cy={70} r={7} />
        <path className="v-vs-scale-ln" d="M140 70 L80 160 M140 70 L200 160 M500 70 L440 160 M500 70 L560 160" />
        <path className="v-vs-scale-pan" d="M70 160 H210 Q140 215 70 160 Z" />
        <path className="v-vs-scale-pan" d="M430 160 H570 Q500 215 430 160 Z" />
      </svg>
      <div className="v-vs-scale-lists">{col(b.a, "a")}{col(b.b, "b")}</div>
    </div>
  );
}

function VsHead({ b, p, limits }: LookProps<"versus">) {
  const side = (s: Side, k: "a" | "b") => (
    <div className={`v-vs-head-col v-vs-head-${k}`}>
      <Txt path={`${p}.${k}.title`} value={s.title} as="h3" max={limits.short} />
      <ol><Items p={`${p}.${k}.items`} items={s.items} max={limits.item} /></ol>
    </div>
  );
  return <div className="v-cp v-vs-head"><div className="v-vs-head-grid">{side(b.a, "a")}{side(b.b, "b")}</div></div>;
}

function VsArrow({ b, p, limits }: LookProps<"versus">) {
  const side = (s: Side, k: "a" | "b") => (
    <div className={`v-vs-arrow-side v-vs-arrow-${k === "a" ? "from" : "to"}`}>
      <Txt path={`${p}.${k}.title`} value={s.title} as="div" className="v-vs-arrow-lbl" max={limits.short} />
      <ul><Items p={`${p}.${k}.items`} items={s.items} max={limits.item} /></ul>
    </div>
  );
  return (
    <div className="v-cp v-vs-arrow">
      <div className="v-vs-arrow-grid">
        {side(b.a, "a")}
        <div className="v-vs-arrow-mid">
          <span className="v-vs-arrow-r"><Ic d="right" /></span>
          <span className="v-vs-arrow-d"><Ic d="down" /></span>
        </div>
        {side(b.b, "b")}
      </div>
    </div>
  );
}

export const VERSUS: Look<"versus">[] = [
  { name: "Mittellinie", family: "grid", View: VsSplit },
  { name: "Haken und Kreuz", family: "grid", fits: (b) => b.tone === "good_bad", View: VsChecks },
  { name: "Zeile für Zeile", family: "grid", View: VsRows },
  { name: "Waage", fits: (b) => b.tone === "good_bad", View: VsScale },
  { name: "Kopflinie", family: "grid", View: VsHead },
  { name: "Vorher und nachher", family: "grid", fits: (b) => b.tone === "neutral", View: VsArrow },
  { name: "Zwei Karten", family: "boxes", View: VsCards },
];
