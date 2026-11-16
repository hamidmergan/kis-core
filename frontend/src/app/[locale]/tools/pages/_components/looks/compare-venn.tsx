"use client";

import { Fragment } from "react";
import type { Side } from "../../_lib/types";
import { Txt } from "../Txt";
import type { Look, LookProps } from "./registry";
import { Items, usePageWords } from "./shared";

function VnTwo({ b, p, limits }: LookProps<"venn">) {
  return (
    <div className="v-cp v-vn-2">
      <div className="v-vn-2-stage">
        <svg className="v-vn-2-wide" viewBox="0 0 640 360" aria-hidden="true">
          <circle className="v-vn-2-c" cx={230} cy={180} r={150} /><circle className="v-vn-2-c" cx={410} cy={180} r={150} />
        </svg>
        <svg className="v-vn-2-tall" viewBox="0 0 360 520" aria-hidden="true">
          <circle className="v-vn-2-c" cx={180} cy={170} r={150} /><circle className="v-vn-2-c" cx={180} cy={350} r={150} />
        </svg>
        <div className="v-vn-2-a">
          <Txt path={`${p}.a.title`} value={b.a.title} as="h3" className="v-vn-2-t" max={limits.short} />
          <ul><Items p={`${p}.a.items`} items={b.a.items} max={limits.short} /></ul>
        </div>
        <div className="v-vn-2-both"><ul><Items p={`${p}.both`} items={b.both} max={limits.short} /></ul></div>
        <div className="v-vn-2-b">
          <Txt path={`${p}.b.title`} value={b.b.title} as="h3" className="v-vn-2-t" max={limits.short} />
          <ul><Items p={`${p}.b.items`} items={b.b.items} max={limits.short} /></ul>
        </div>
      </div>
    </div>
  );
}

function VnThree({ b, p, limits }: LookProps<"venn">) {
  const w = usePageWords();
  const c: Side = b.c ?? { title: "", items: [] };
  const title = (k: "a" | "b" | "c", s: Side) => (
    <Txt path={`${p}.${k}.title`} value={s.title} as="h3" className={`v-vn-3-lay v-vn-3-t v-vn-3-t${k}`} max={limits.short} />
  );
  const items = (k: "a" | "b" | "c", s: Side) => (
    <ul className={`v-vn-3-lay v-vn-3-i${k}`}><Items p={`${p}.${k}.items`} items={s.items} max={limits.short} /></ul>
  );
  const row = (k: "a" | "b" | "c" | "both", s: Side) => (
    <li>
      {k === "both" ? <b>{w.both}</b> : <Txt path={`${p}.${k}.title`} value={s.title} as="b" max={limits.short} />}
      {s.items.map((t, i) => (
        <Fragment key={i}>
          {i > 0 && ", "}
          <Txt path={k === "both" ? `${p}.both.${i}` : `${p}.${k}.items.${i}`} value={t} max={limits.short} />
        </Fragment>
      ))}
    </li>
  );
  return (
    <div className="v-cp v-vn-3">
      <div className="v-vn-3-stage">
        <svg viewBox="0 0 640 490" aria-hidden="true">
          <circle className="v-vn-3-c" cx={240} cy={190} r={150} /><circle className="v-vn-3-c" cx={400} cy={190} r={150} /><circle className="v-vn-3-c" cx={320} cy={330} r={150} />
        </svg>
        {title("a", b.a)}{title("b", b.b)}{title("c", c)}
        {items("a", b.a)}{items("b", b.b)}{items("c", c)}
        <ul className="v-vn-3-lay v-vn-3-both"><Items p={`${p}.both`} items={b.both} max={limits.short} /></ul>
      </div>
      {/* On a phone the circles give way to a list, the shared part last. */}
      <ul className="v-vn-3-list">
        {row("a", b.a)}{row("b", b.b)}{row("c", c)}
        {row("both", { title: "", items: b.both })}
      </ul>
    </div>
  );
}

export const VENN: Look<"venn">[] = [
  { name: "Zwei Kreise", View: VnTwo },
  { name: "Drei Kreise", fits: (b) => !!b.c, View: VnThree },
];
