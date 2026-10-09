"use client";

import { Fragment, useContext, type CSSProperties } from "react";
import type { Block, Limits, Side } from "../../_lib/types";
import type { LookProps, Looks } from "./registry";
import { EditCtx, Txt } from "../Txt";
import { usePageWords } from "./shared";
import "./compare.css";

type MatrixBlock = Extract<Block, { kind: "matrix" }>;
type Pos = MatrixBlock["cells"][number]["pos"];
const POS: Pos[] = ["tl", "tr", "bl", "br"];

// Simple line icons drawn in the current colour.
const PATH = {
  check: "M5 12.5l4.5 4.5L19 7.5",
  cross: "M6 6l12 12M18 6L6 18",
  right: "M4 12h16M13 5l7 7-7 7",
  down: "M12 4v16M5 13l7 7 7-7",
};
function Ic({ d }: { d: keyof typeof PATH }) {
  return <svg className="v-cp-ic" viewBox="0 0 24 24" aria-hidden="true"><path d={PATH[d]} /></svg>;
}

/** The items of a list, every one deletable on its own. */
function Items({ p, items, max }: { p: string; items: string[]; max: number }) {
  return (
    <>
      {items.map((t, i) => (
        <li key={i} data-d={`${p}.${i}`}><Txt path={`${p}.${i}`} value={t} max={max} /></li>
      ))}
    </>
  );
}

// ---------- versus ----------

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

// ---------- matrix ----------

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

// ---------- venn ----------

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

// ---------- formula ----------

/** A formula never breaks, its size follows its length so it fits the width it has. */
const fit = (key: string) => ({ "--fm-len": Math.max(8, key.length) }) as CSSProperties;

/** The formula on one line with its sentence below, shared with the old highlight. */
function Big({ p, keyText, text, limits }: { p: string; keyText: string; text: string; limits: Limits }) {
  return (
    <div className="v-cp v-fm" style={fit(keyText)}>
      <Txt path={`${p}.key`} value={keyText} as="div" className="v-fm-key" max={limits.short} />
      <Txt path={`${p}.text`} value={text} as="p" className="v-fm-text" max={limits.item} />
    </div>
  );
}

function FmBig({ b, p, limits }: LookProps<"formula">) {
  return <Big p={p} keyText={b.key} text={b.text} limits={limits} />;
}

function FmLegend({ b, p, limits }: LookProps<"formula">) {
  return (
    <div className="v-cp v-fm" style={fit(b.key)}>
      <Txt path={`${p}.key`} value={b.key} as="div" className="v-fm-key" max={limits.short} />
      <dl className="v-fm-parts">
        {b.parts.map((x, i) => (
          <div key={i} data-d={`${p}.parts.${i}`}>
            <Txt path={`${p}.parts.${i}.sym`} value={x.sym} as="dt" max={limits.short} />
            <Txt path={`${p}.parts.${i}.text`} value={x.text} as="dd" max={limits.item} />
          </div>
        ))}
      </dl>
      <Txt path={`${p}.text`} value={b.text} as="p" className="v-fm-text" max={limits.item} />
    </div>
  );
}

function FmWay({ b, p, limits }: LookProps<"formula">) {
  return (
    <div className="v-cp v-fm" style={fit(b.key)}>
      <Txt path={`${p}.key`} value={b.key} as="div" className="v-fm-key" max={limits.short} />
      <ol className="v-fm-lines">
        {b.example.map((l, i) => (
          <li key={i} data-d={`${p}.example.${i}`}>
            <Txt path={`${p}.example.${i}`} value={l} max={limits.item} />
          </li>
        ))}
      </ol>
      <Txt path={`${p}.text`} value={b.text} as="p" className="v-fm-text" max={limits.item} />
    </div>
  );
}

// ---------- mistakes ----------

function MkPairs({ b, p, limits }: LookProps<"mistakes">) {
  return (
    <div className="v-cp v-mk-pair">
      <ul className="v-mk-pair-list">
        {b.pairs.map((m, i) => (
          <li key={i} data-d={`${p}.pairs.${i}`}>
            <div className="v-mk-pair-w"><Ic d="cross" /><Txt path={`${p}.pairs.${i}.wrong`} value={m.wrong} max={limits.item} /></div>
            <div className="v-mk-pair-r"><Ic d="check" /><Txt path={`${p}.pairs.${i}.right`} value={m.right} max={limits.item} /></div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MkStrike({ b, p, limits }: LookProps<"mistakes">) {
  // Two or four pairs stand in two columns, otherwise three, so five end as three and two.
  const n = b.pairs.length;
  const cols = n <= 2 || n === 4 ? 2 : 3;
  return (
    <div className="v-cp v-mk-strike">
      <div className="v-mk-strike-grid" style={{ "--v-cols": cols } as CSSProperties}>
        {b.pairs.map((m, i) => (
          <div className="v-mk-strike-item" key={i} data-d={`${p}.pairs.${i}`}>
            <Txt path={`${p}.pairs.${i}.wrong`} value={m.wrong} as="s" max={limits.item} />
            <Txt path={`${p}.pairs.${i}.right`} value={m.right} as="p" max={limits.item} />
          </div>
        ))}
      </div>
    </div>
  );
}

function MkTable({ b, p, limits }: LookProps<"mistakes">) {
  const w = usePageWords();
  return (
    <div className="v-cp v-mk-tab">
      <table className="v-mk-tab-t">
        <thead>
          <tr>
            <th className="v-mk-tab-bad"><span><Ic d="cross" />{w.wrong}</span></th>
            <th className="v-mk-tab-good"><span><Ic d="check" />{w.right}</span></th>
          </tr>
        </thead>
        <tbody>
          {b.pairs.map((m, i) => (
            <tr key={i} data-d={`${p}.pairs.${i}`}>
              <td><Txt path={`${p}.pairs.${i}.wrong`} value={m.wrong} as="div" max={limits.item} keep /></td>
              <td><Txt path={`${p}.pairs.${i}.right`} value={m.right} as="div" max={limits.item} keep /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MkArrow({ b, p, limits }: LookProps<"mistakes">) {
  return (
    <div className="v-cp v-mk-arr">
      {b.pairs.map((m, i) => (
        <div className="v-mk-arr-row" key={i} data-d={`${p}.pairs.${i}`}>
          <div className="v-mk-arr-w"><Txt path={`${p}.pairs.${i}.wrong`} value={m.wrong} max={limits.item} /></div>
          <div className="v-mk-arr-a"><Ic d="right" /></div>
          <div className="v-mk-arr-r"><Txt path={`${p}.pairs.${i}.right`} value={m.right} max={limits.item} /></div>
        </div>
      ))}
    </div>
  );
}

// ---------- example ----------

function ExRows({ b, p, limits }: LookProps<"example">) {
  const w = usePageWords();
  const { editing } = useContext(EditCtx);
  const row = (lbl: string, body: React.ReactNode) => (
    <div className="v-ex-rows-row"><div className="v-ex-rows-lbl">{lbl}</div><div className="v-ex-rows-body">{body}</div></div>
  );
  return (
    <div className="v-cp v-ex-rows">
      <Txt path={`${p}.title`} value={b.title} as="h3" className="v-ex-rows-title" max={limits.short} />
      {(b.situation || editing) && row(w.situation, <Txt path={`${p}.situation`} value={b.situation} as="p" max={limits.item} />)}
      {b.steps.length > 0 && row(w.approach, (
        <ol className="v-ex-rows-steps"><Items p={`${p}.steps`} items={b.steps} max={limits.item} /></ol>
      ))}
      {(b.result || editing) && row(w.result, <Txt path={`${p}.result`} value={b.result} as="p" className="v-ex-rows-res" max={limits.item} />)}
    </div>
  );
}

function ExCalc({ b, p, limits }: LookProps<"example">) {
  return (
    <div className="v-cp v-ex-calc">
      <Txt path={`${p}.title`} value={b.title} as="h3" max={limits.short} />
      <Txt path={`${p}.situation`} value={b.situation} as="p" className="v-ex-calc-sit" max={limits.item} />
      <div className="v-ex-calc-block">
        {b.steps.map((s, i) => (
          <div className="v-ex-calc-line" key={i} data-d={`${p}.steps.${i}`}><Txt path={`${p}.steps.${i}`} value={s} max={limits.item} /></div>
        ))}
        <div className="v-ex-calc-res"><Txt path={`${p}.result`} value={b.result} max={limits.item} /></div>
      </div>
    </div>
  );
}

function ExRail({ b, p, limits }: LookProps<"example">) {
  const w = usePageWords();
  const { editing } = useContext(EditCtx);
  const part = (lbl: string, body: React.ReactNode, cls = "") => (
    <div className={`v-ex-rail-part ${cls}`}><span className="v-ex-rail-lbl">{lbl}</span>{body}</div>
  );
  return (
    <div className="v-cp v-ex-rail">
      <Txt path={`${p}.title`} value={b.title} as="h3" className="v-ex-rail-title" max={limits.short} />
      <div className="v-ex-rail-line">
        {(b.situation || editing) && part(w.situation, <Txt path={`${p}.situation`} value={b.situation} as="p" max={limits.item} />)}
        {b.steps.length > 0 && part(w.approach, b.steps.map((s, i) => (
          <Txt key={i} path={`${p}.steps.${i}`} value={s} as="p" max={limits.item} />
        )))}
        {(b.result || editing) && part(w.result, <Txt path={`${p}.result`} value={b.result} as="p" max={limits.item} />, "v-ex-rail-res")}
      </div>
    </div>
  );
}

// ---------- highlight of older pages ----------

// A key with an equals sign or an operator between operands is a formula, anything else a term.
const FORMULA = /=|[+×·÷√^]|\s[-−/]\s/;

function HlLook({ b, p, limits }: LookProps<"highlight">) {
  if (FORMULA.test(b.key)) return <Big p={p} keyText={b.key} text={b.text} limits={limits} />;
  return (
    <div className="v-cp v-hl">
      <div className="v-hl-term">
        <Txt path={`${p}.key`} value={b.key} as="div" className="v-hl-term-k" max={limits.short} />
        <Txt path={`${p}.text`} value={b.text} as="p" className="v-hl-term-x" max={limits.item} />
      </div>
    </div>
  );
}

export const LOOKS_COMPARE: Looks = {
  versus: [
    { name: "Mittellinie", View: VsSplit },
    { name: "Haken und Kreuz", fits: (b) => b.tone === "good_bad", View: VsChecks },
    { name: "Zeile für Zeile", View: VsRows },
    { name: "Waage", fits: (b) => b.tone === "good_bad", View: VsScale },
    { name: "Kopflinie", View: VsHead },
    { name: "Vorher und nachher", fits: (b) => b.tone === "neutral", View: VsArrow },
  ],
  matrix: [
    { name: "Vier Felder", View: MxFields },
    { name: "Punkte im Kreuz", fits: (b) => b.points.length >= 2, View: MxPoints },
    { name: "Achsenkreuz", View: MxCross },
  ],
  venn: [
    { name: "Zwei Kreise", View: VnTwo },
    { name: "Drei Kreise", fits: (b) => !!b.c, View: VnThree },
  ],
  formula: [
    { name: "Groß zentriert", View: FmBig },
    { name: "Mit Legende", fits: (b) => b.parts.length > 0, View: FmLegend },
    { name: "Rechenweg", fits: (b) => b.example.length > 0, View: FmWay },
  ],
  mistakes: [
    { name: "Kreuz und Haken", View: MkPairs },
    { name: "Durchgestrichen", View: MkStrike },
    { name: "Tabelle", View: MkTable },
    { name: "Pfeil", View: MkArrow },
  ],
  example: [
    { name: "Drei Zeilen", View: ExRows },
    { name: "Rechenbeispiel", View: ExCalc },
    { name: "Erzählleiste", View: ExRail },
  ],
  highlight: [{ name: "Formel oder Begriff", View: HlLook }],
};
