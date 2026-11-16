"use client";

import type { Block, Limits } from "../../_lib/types";
import { Txt } from "../Txt";
import type { Look, LookProps } from "./registry";
import { usePageWords } from "./shared";

type MatrixBlock = Extract<Block, { kind: "matrix" }>;
type Pos = MatrixBlock["cells"][number]["pos"];
const POS: Pos[] = ["tl", "tr", "bl", "br"];

/** One quadrant with its title and text, empty when the page has no cell for it. */
function Quadrant({ b, p, pos, cls, limits }: { b: MatrixBlock; p: string; pos: Pos; cls: string; limits: Limits }) {
  const i = b.cells.findIndex((c) => c.pos === pos);
  const c = b.cells[i];
  return (
    <div className={cls} data-d={c ? `${p}.cells.${i}` : undefined}>
      {c && (
        <>
          <Txt path={`${p}.cells.${i}.title`} value={c.title} as="h3" max={limits.short} />
          <Txt path={`${p}.cells.${i}.text`} value={c.text} as="p" max={limits.item} />
        </>
      )}
    </div>
  );
}

function MxFields({ b, p, limits }: LookProps<"matrix">) {
  const w = usePageWords();
  return (
    <div className="v-cp v-mx-f">
      <div className="v-mx-f-wrap">
        <div className="v-mx-f-y">
          <span>{w.low}</span>
          <Txt path={`${p}.y`} value={b.y} className="v-mx-f-name" max={limits.short} />
          <span>{w.high}</span>
        </div>
        <div className="v-mx-f-cells">
          {POS.map((pos) => <Quadrant key={pos} b={b} p={p} pos={pos} cls={`v-mx-f-cell v-mx-f-${pos}`} limits={limits} />)}
        </div>
        <div className="v-mx-f-x">
          <span>{w.low}</span>
          <Txt path={`${p}.x`} value={b.x} className="v-mx-f-name" max={limits.short} />
          <span>{w.high}</span>
        </div>
      </div>
    </div>
  );
}

const unit = (v: number) => Math.min(1, Math.max(0, v));

function MxPoints({ b, p, limits }: LookProps<"matrix">) {
  const quadrant = (pt: MatrixBlock["points"][number]) =>
    b.cells.find((c) => c.pos === `${pt.y > 0.5 ? "t" : "b"}${pt.x > 0.5 ? "r" : "l"}`)?.title ?? "";
  return (
    <div className="v-cp v-mx-p">
      <div className="v-mx-p-fig">
        <div className="v-mx-p-y"><Txt path={`${p}.y`} value={b.y} max={limits.short} />{" →"}</div>
        <div className="v-mx-p-frame">
          <i className="v-mx-p-mv" /><i className="v-mx-p-mh" />
          {POS.map((pos) => {
            const i = b.cells.findIndex((c) => c.pos === pos);
            const c = b.cells[i];
            return c ? <Txt key={pos} path={`${p}.cells.${i}.title`} value={c.title} className={`v-mx-p-q v-mx-p-${pos}`} max={limits.short} /> : null;
          })}
          {b.points.map((pt, i) => (
            <div key={i} className={`v-mx-p-pt${pt.x > 0.5 ? " is-left" : ""}`} data-d={`${p}.points.${i}`}
              style={{ left: `${unit(pt.x) * 100}%`, top: `${(1 - unit(pt.y)) * 100}%` }}>
              <i />
              <Txt path={`${p}.points.${i}.label`} value={pt.label} className="v-mx-p-lbl" max={limits.short} />
            </div>
          ))}
        </div>
        <div className="v-mx-p-x"><Txt path={`${p}.x`} value={b.x} max={limits.short} />{" →"}</div>
      </div>
      {/* On a phone the same points stand in a list with the field they fall into. */}
      <ul className="v-mx-p-list">
        {b.points.map((pt, i) => (
          <li key={i} data-d={`${p}.points.${i}`}>
            <Txt path={`${p}.points.${i}.label`} value={pt.label} as="b" max={limits.short} />
            <span>{quadrant(pt)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MxCross({ b, p, limits }: LookProps<"matrix">) {
  return (
    <div className="v-cp v-mx-x">
      <div className="v-mx-x-wrap">
        <Txt path={`${p}.y`} value={b.y} className="v-mx-x-ylbl" max={limits.short} />
        <Txt path={`${p}.x`} value={b.x} className="v-mx-x-xlbl" max={limits.short} />
        <i className="v-mx-x-v" /><i className="v-mx-x-h" />
        <svg className="v-mx-x-tip v-mx-x-tipv" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 11l7-8 7 8" /></svg>
        <svg className="v-mx-x-tip v-mx-x-tiph" viewBox="0 0 18 18" aria-hidden="true"><path d="M7 2l8 7-8 7" /></svg>
        <div className="v-mx-x-grid">
          {POS.map((pos) => <Quadrant key={pos} b={b} p={p} pos={pos} cls={`v-mx-x-q v-mx-x-${pos}`} limits={limits} />)}
        </div>
      </div>
    </div>
  );
}

export const MATRIX: Look<"matrix">[] = [
  { name: "Vier Felder", family: "grid", View: MxFields },
  { name: "Punkte im Kreuz", fits: (b) => b.points.length >= 2, View: MxPoints },
  { name: "Achsenkreuz", View: MxCross },
];
