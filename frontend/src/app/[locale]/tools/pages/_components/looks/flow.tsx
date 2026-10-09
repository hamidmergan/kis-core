"use client";

import { useContext, type CSSProperties } from "react";
import type { Block } from "../../_lib/types";
import type { LookProps, Looks } from "./registry";
import { usePageWords } from "./shared";
import { EditCtx, Txt } from "../Txt";
import { useNumber } from "../Charts";
import "./flow.css";

type Steps = Extract<Block, { kind: "steps" }>;
type Cycle = Extract<Block, { kind: "cycle" }>;
type Timeline = Extract<Block, { kind: "timeline" }>;
type Tree = Extract<Block, { kind: "tree" }>;
type Levels = Extract<Block, { kind: "levels" }>;

/** CSS custom properties as inline style. */
const vars = (v: Record<string, string | number>): CSSProperties => v as CSSProperties;

/** A point on a circle, the angle in degrees clockwise from the top. */
function pt(cx: number, cy: number, r: number, deg: number): [number, number] {
  const a = ((deg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}
const f1 = (n: number) => n.toFixed(1);
const pc = (n: number, of: number) => `${((n / of) * 100).toFixed(2)}%`;

/** The first column count whose last row is full or at least half full with two items. */
function colsFor(n: number, prefs: number[]): number {
  return prefs.find((c) => n % c === 0 || (n % c >= 2 && (n % c) * 2 >= c)) ?? prefs[0];
}

function Arrow() {
  return <svg className="v-fl-arr" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h16M13 6l6 6-6 6" /></svg>;
}

function Dot({ n }: { n: number }) {
  const fmt = useNumber();
  return <span className="v-fl-dot">{fmt(n)}</span>;
}

/* ---------------- steps ---------------- */

function StepsLine({ b, p, limits }: LookProps<"steps">) {
  return (
    <div className="v-fl v-fl-line"><ol className="v-fl-line-list">
      {b.steps.map((s, i) => (
        <li className="v-fl-line-item" key={i} data-d={`${p}.steps.${i}`}>
          <Dot n={i + 1} />
          <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
          <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
        </li>
      ))}
    </ol></div>
  );
}

function StepsStepper({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  return (
    <div className="v-fl v-fl-stp"><ol className="v-fl-stp-row" style={vars({ "--n": b.steps.length })}>
      {b.steps.map((s, i) => (
        <li className="v-fl-stp-item" key={i} data-d={`${p}.steps.${i}`}>
          <span className="v-fl-stp-node">{fmt(i + 1)}</span>
          <div className="v-fl-stp-body">
            <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
            <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function StepsChevron({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  return (
    <div className="v-fl v-fl-chev"><ol className="v-fl-chev-row" style={vars({ "--n": b.steps.length })}>
      {b.steps.map((s, i) => (
        <li className="v-fl-chev-item" key={i} data-d={`${p}.steps.${i}`}>
          <div className="v-fl-chev-box">
            <svg className="v-fl-chev-bg" viewBox="0 0 200 90" preserveAspectRatio="none" aria-hidden="true">
              <path className="v-fl-chev-shape" vectorEffect="non-scaling-stroke" d={i ? "M2 2 L176 2 L198 45 L176 88 L2 88 L24 45 Z" : "M2 2 L176 2 L198 45 L176 88 L2 88 Z"} />
            </svg>
            <span className="v-fl-chev-no">{fmt(i + 1)}</span>
            <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
          </div>
          <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
        </li>
      ))}
    </ol></div>
  );
}

function StepsStair({ b, p, limits }: LookProps<"steps">) {
  const n = Math.max(2, b.steps.length);
  const style = vars({ "--o": Math.min(11, 60 / (n - 1)).toFixed(2), "--op": Math.min(7, 36 / (n - 1)).toFixed(2) });
  return (
    <div className="v-fl v-fl-stair"><ol className="v-fl-stair-list" style={style}>
      {b.steps.map((s, i) => (
        <li className="v-fl-stair-step" key={i} data-d={`${p}.steps.${i}`} style={vars({ "--i": i })}>
          <Dot n={i + 1} />
          <div>
            <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
            <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function StepsBig({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  const n = b.steps.length;
  // Up to six stand in one row, seven and eight break into rows of four.
  const cols = n <= 6 ? n : 4;
  return (
    <div className="v-fl v-fl-big"><ol className="v-fl-big-row" style={vars({ "--n": cols })}>
      {b.steps.map((s, i) => (
        <li className={`v-fl-big-col${i % cols === 0 ? " v-fl-big-first" : ""}${i >= cols ? " v-fl-big-more" : ""}`} key={i} data-d={`${p}.steps.${i}`}>
          <span className="v-fl-big-no">{fmt(i + 1)}</span>
          <div>
            <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
            <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function StepsZig({ b, p, limits }: LookProps<"steps">) {
  return (
    <div className="v-fl v-fl-zig"><ol className="v-fl-zig-grid">
      {b.steps.map((s, i) => (
        <li className={`v-fl-zig-item ${i % 2 ? "v-fl-zig-r" : "v-fl-zig-l"}`} key={i} data-d={`${p}.steps.${i}`} style={{ gridRow: i + 1 }}>
          <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
          <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
        </li>
      ))}
      {b.steps.map((_, i) => (
        <li className="v-fl-zig-mark" key={`m${i}`} style={{ gridRow: i + 1 }} aria-hidden="true"><Dot n={i + 1} /></li>
      ))}
    </ol></div>
  );
}

function StepsIndex({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  return (
    <div className="v-fl v-fl-idx"><ol className="v-fl-idx-list">
      {b.steps.map((s, i) => (
        <li className="v-fl-idx-row" key={i} data-d={`${p}.steps.${i}`}>
          <span className="v-fl-idx-no">{fmt(i + 1).padStart(2, "0")}</span>
          <div>
            <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
            <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

/** Rows of at most three stations, never one alone. */
function flowRows(n: number): number[] {
  const rows: number[] = [];
  let left = n;
  while (left > 3) {
    if (left === 4) { rows.push(2, 2); left = 0; } else { rows.push(3); left -= 3; }
  }
  if (left > 0) rows.push(left);
  return rows;
}

function StepsFlow({ b, p, limits }: LookProps<"steps">) {
  const fmt = useNumber();
  const w = usePageWords();
  const rows = flowRows(b.steps.length);
  // The centre of a station in a row of three or two, measured from the row's edge.
  const edge = (k: number) => (k === 3 ? "calc(16.667% - 16px)" : "calc(33.333% - 8px)");
  let at = 0;
  return (
    <div className="v-fl v-fl-flow">
      {rows.map((k, r) => {
        const first = at;
        at += k;
        return (
          <div key={r}>
            {r > 0 && (
              <>
                <div className="v-fl-flow-elbow" aria-hidden="true" style={vars({ "--el": edge(k), "--er": edge(rows[r - 1]) })}><i /></div>
                <div className="v-fl-flow-down" aria-hidden="true"><Arrow /></div>
              </>
            )}
            <ol className="v-fl-flow-row">
              {b.steps.slice(first, first + k).map((s, j) => {
                const i = first + j;
                return (
                  <li className="v-fl-flow-st" key={i} data-d={`${p}.steps.${i}`}>
                    <span className="v-fl-flow-no">{`${w.step} ${fmt(i + 1)}`}</span>
                    <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
                    <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
                  </li>
                );
              }).flatMap((el, j) => (j ? [<li className="v-fl-flow-a" key={`a${first + j}`} aria-hidden="true"><Arrow /></li>, el] : [el]))}
            </ol>
          </div>
        );
      })}
    </div>
  );
}

/* ---------------- cycle ---------------- */

function CycleRing({ b, p, limits }: LookProps<"cycle">) {
  const fmt = useNumber();
  const S = b.steps, n = S.length, cx = 210, cy = 210, R = 140, span = 360 / n, start = span / 2;
  const arcs = S.map((_, i) => {
    const a = start + span * i, [x1, y1] = pt(cx, cy, R, a + 24), [x2, y2] = pt(cx, cy, R, a + span - 28);
    return `M${f1(x1)} ${f1(y1)} A${R} ${R} 0 0 1 ${f1(x2)} ${f1(y2)}`;
  });
  const nodes = S.map((_, i) => pt(cx, cy, R, start + span * i));
  return (
    <div className="v-fl v-fl-ring"><div className="v-fl-ring-grid">
      <div className="v-fl-box v-fl-ring-box">
        <svg className="v-fl-ring-svg" viewBox="0 0 420 420" aria-hidden="true">
          <defs>
            <marker id={`v-fl-ring-m-${p.replace(/\W/g, "-")}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path className="v-fl-ring-head" d="M0 0L10 5L0 10z" />
            </marker>
          </defs>
          {arcs.map((d, i) => <path className="v-fl-ring-arc" key={i} d={d} markerEnd={`url(#v-fl-ring-m-${p.replace(/\W/g, "-")})`} />)}
          {nodes.map(([x, y], i) => <circle className="v-fl-ring-node" key={i} cx={f1(x)} cy={f1(y)} r="50" />)}
        </svg>
        {nodes.map(([x, y], i) => (
          <div className="v-fl-lbl v-fl-ring-lbl" key={i} style={{ left: pc(x, 420), top: pc(y, 420) }}>
            <i>{fmt(i + 1)}</i>
            <Txt path={`${p}.steps.${i}.title`} value={S[i].title} as="b" max={limits.short} />
          </div>
        ))}
        <Txt path={`${p}.center`} value={b.center} as="div" className="v-fl-lbl v-fl-ring-center" max={limits.short} />
      </div>
      {S.map((s, i) => (
        <div className="v-fl-ring-txt" key={i} data-c={i + 1} data-d={`${p}.steps.${i}`}>
          <h3>{fmt(i + 1)} <Txt path={`${p}.steps.${i}.title`} value={s.title} max={limits.short} /></h3>
          <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
        </div>
      ))}
    </div></div>
  );
}

function CycleRingList({ b, p, limits }: LookProps<"cycle">) {
  const fmt = useNumber();
  const S = b.steps, n = S.length, cx = 120, cy = 120, r = 88, span = 360 / n;
  return (
    <div className="v-fl v-fl-rl"><div className="v-fl-rl-grid">
      <div className="v-fl-box v-fl-rl-box">
        <svg className="v-fl-rl-svg" viewBox="0 0 240 240" aria-hidden="true">
          <circle className="v-fl-rl-circle" cx={cx} cy={cy} r={r} />
          {S.map((_, i) => {
            const [hx, hy] = pt(cx, cy, r, span * i + span / 2), [x, y] = pt(cx, cy, r, span * i);
            return (
              <g key={i}>
                <path className="v-fl-ring-head" d="M-7 -6 L7 0 L-7 6z" transform={`translate(${f1(hx)} ${f1(hy)}) rotate(${f1(span * i + span / 2)})`} />
                <circle className="v-fl-rl-dot" cx={f1(x)} cy={f1(y)} r="17" />
                <text className="v-fl-rl-no" x={f1(x)} y={f1(y + 5.5)} textAnchor="middle">{fmt(i + 1)}</text>
              </g>
            );
          })}
        </svg>
        <Txt path={`${p}.center`} value={b.center} as="div" className="v-fl-lbl v-fl-rl-center" max={limits.short} />
      </div>
      <ol className="v-fl-rl-list">
        {S.map((s, i) => (
          <li key={i} data-d={`${p}.steps.${i}`}>
            <Dot n={i + 1} />
            <div>
              <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
              <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
            </div>
          </li>
        ))}
      </ol>
    </div></div>
  );
}

function CycleChain({ b, p, limits }: LookProps<"cycle">) {
  const n = b.steps.length;
  const style = vars({
    "--cols": Array(n).fill("minmax(0, 1fr)").join(" 24px "),
    "--ux": `calc(${(50 / n).toFixed(3)}% - ${(((n - 1) * 24) / n).toFixed(1)}px)`,
  });
  return (
    <div className="v-fl v-fl-chain"><div className="v-fl-chain-wrap" style={style}>
      <ol className="v-fl-chain-row">
        {b.steps.map((s, i) => (
          <li className="v-fl-chain-st" key={i} data-d={`${p}.steps.${i}`}>
            <Dot n={i + 1} />
            <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
            <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
          </li>
        )).flatMap((el, i) => (i ? [<li className="v-fl-chain-a" key={`a${i}`} aria-hidden="true"><Arrow /></li>, el] : [el]))}
      </ol>
      <div className="v-fl-chain-back" aria-hidden="true" />
    </div></div>
  );
}

function CycleDonut({ b, p, limits }: LookProps<"cycle">) {
  const fmt = useNumber();
  const S = b.steps, n = S.length, cx = 160, cy = 160, R = 150, r = 88, span = 360 / n, gap = 2.5;
  // Short titles stand in their segment, longer ones only in the list beside.
  const inSeg = S.every((s) => s.title.length <= 10);
  return (
    <div className="v-fl v-fl-dn"><div className="v-fl-dn-grid">
      <div className="v-fl-box v-fl-dn-box">
        <svg className="v-fl-dn-svg" viewBox="0 0 320 320" aria-hidden="true">
          {S.map((_, i) => {
            const a = span * i + gap, c = span * (i + 1) - gap;
            const [ox1, oy1] = pt(cx, cy, R, a), [ox2, oy2] = pt(cx, cy, R, c), [ix1, iy1] = pt(cx, cy, r, a), [ix2, iy2] = pt(cx, cy, r, c);
            const big = c - a > 180 ? 1 : 0;
            return <path className="v-fl-dn-seg" key={i} d={`M${f1(ox1)} ${f1(oy1)} A${R} ${R} 0 ${big} 1 ${f1(ox2)} ${f1(oy2)} L${f1(ix2)} ${f1(iy2)} A${r} ${r} 0 ${big} 0 ${f1(ix1)} ${f1(iy1)} Z`} />;
          })}
        </svg>
        {S.map((s, i) => {
          const [tx, ty] = pt(cx, cy, (R + r) / 2, span * i + span / 2);
          return (
            <div className={`v-fl-lbl v-fl-dn-lbl${inSeg ? "" : " v-fl-dn-only"}`} key={i} style={{ left: pc(tx, 320), top: pc(ty, 320) }}>
              <i>{fmt(i + 1)}</i>
              {inSeg && <Txt path={`${p}.steps.${i}.title`} value={s.title} as="b" max={limits.short} />}
            </div>
          );
        })}
        <Txt path={`${p}.center`} value={b.center} as="div" className="v-fl-lbl v-fl-dn-center" max={limits.short} />
      </div>
      <ol className="v-fl-dn-list" style={vars({ "--lc": n % 2 === 0 ? 2 : 1 })}>
        {S.map((s, i) => (
          <li key={i} data-d={`${p}.steps.${i}`}>
            <span className="v-fl-dn-key">{fmt(i + 1)}</span>
            <div>
              <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={limits.short} />
              <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={limits.item} />
            </div>
          </li>
        ))}
      </ol>
    </div></div>
  );
}

/* ---------------- timeline ---------------- */

function TlVertical({ b, p, limits }: LookProps<"timeline">) {
  return (
    <div className="v-fl v-fl-tl"><ol className="v-fl-tl-list">
      {b.events.map((t, i) => (
        <li className="v-fl-tl-row" key={i} data-d={`${p}.events.${i}`}>
          <Txt path={`${p}.events.${i}.date`} value={t.date} className="v-fl-tl-date" max={limits.short} />
          <span className="v-fl-tl-mark" aria-hidden="true" />
          <div>
            <Txt path={`${p}.events.${i}.title`} value={t.title} as="h3" max={limits.short} />
            <Txt path={`${p}.events.${i}.text`} value={t.text} as="p" max={limits.item} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function TlHorizontal({ b, p, limits }: LookProps<"timeline">) {
  const n = b.events.length;
  return (
    <div className="v-fl v-fl-th"><ol className="v-fl-th-row" style={vars({ "--n": n })}>
      {b.events.map((t, i) => (
        <li className={`v-fl-th-item${i === n - 1 ? " v-fl-th-last" : ""}`} key={i} data-d={`${p}.events.${i}`}>
          <Txt path={`${p}.events.${i}.date`} value={t.date} className="v-fl-th-date" max={limits.short} />
          <span className="v-fl-th-tick" aria-hidden="true" />
          <Txt path={`${p}.events.${i}.title`} value={t.title} as="h3" max={limits.short} />
          <Txt path={`${p}.events.${i}.text`} value={t.text} as="p" max={limits.item} />
        </li>
      ))}
    </ol></div>
  );
}

function TlZig({ b, p, limits }: LookProps<"timeline">) {
  return (
    <div className="v-fl v-fl-tz"><ol className="v-fl-tz-grid">
      {b.events.map((t, i) => (
        <li className={`v-fl-tz-item ${i % 2 ? "v-fl-tz-r" : "v-fl-tz-l"}`} key={i} data-d={`${p}.events.${i}`} style={{ gridRow: i + 1 }}>
          <Txt path={`${p}.events.${i}.title`} value={t.title} as="h3" max={limits.short} />
          <Txt path={`${p}.events.${i}.text`} value={t.text} as="p" max={limits.item} />
        </li>
      ))}
      {b.events.map((t, i) => (
        <li className="v-fl-tz-year" key={`y${i}`} style={{ gridRow: i + 1 }}>
          <Txt path={`${p}.events.${i}.date`} value={t.date} max={limits.short} />
        </li>
      ))}
    </ol></div>
  );
}

function TlDiamond({ b, p, limits }: LookProps<"timeline">) {
  const n = b.events.length;
  const cols = n <= 3 ? n : n === 4 ? 2 : n <= 6 ? 3 : 4;
  return (
    <div className="v-fl v-fl-ms"><ol className="v-fl-ms-grid" style={vars({ "--c": cols })}>
      {b.events.map((t, i) => (
        <li className={`v-fl-ms-item${i % cols === 0 ? " v-fl-ms-first" : ""}${i % cols === cols - 1 || i === n - 1 ? " v-fl-ms-end" : ""}`} key={i} data-d={`${p}.events.${i}`}>
          <div className="v-fl-box v-fl-ms-box">
            <svg className="v-fl-ms-svg" viewBox="0 0 72 72" aria-hidden="true"><path className="v-fl-ms-shape" d="M36 3 L69 36 L36 69 L3 36 Z" /></svg>
            <Txt path={`${p}.events.${i}.date`} value={t.date} as="div" className={`v-fl-lbl v-fl-ms-year${t.date.length > 4 ? " v-fl-ms-long" : ""}`} max={limits.short} />
          </div>
          <div>
            <Txt path={`${p}.events.${i}.title`} value={t.title} as="h3" max={limits.short} />
            <Txt path={`${p}.events.${i}.text`} value={t.text} as="p" max={limits.item} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

function TlBig({ b, p, limits }: LookProps<"timeline">) {
  const n = b.events.length;
  const cols = colsFor(n, [2, 3, 4]);
  const lastRow = n % cols === 0 ? cols : n % cols;
  return (
    <div className="v-fl v-fl-ty"><ol className="v-fl-ty-grid" style={vars({ "--c": cols })}>
      {b.events.map((t, i) => (
        <li className={`v-fl-ty-item${i >= n - lastRow ? " v-fl-ty-last" : ""}`} key={i} data-d={`${p}.events.${i}`}>
          <Txt path={`${p}.events.${i}.date`} value={t.date} className={`v-fl-ty-year${t.date.length > 5 ? " v-fl-ty-small" : ""}`} max={limits.short} />
          <div>
            <Txt path={`${p}.events.${i}.title`} value={t.title} as="h3" max={limits.short} />
            <Txt path={`${p}.events.${i}.text`} value={t.text} as="p" max={limits.item} />
          </div>
        </li>
      ))}
    </ol></div>
  );
}

/* ---------------- tree ---------------- */

function TreeOrg({ b, p, limits }: LookProps<"tree">) {
  const n = b.branches.length;
  // The bar runs from the first branch's centre to the last one's; many branches hang their leaves further left.
  const style = vars({ "--n": n, "--bx": `calc(${(50 / n).toFixed(3)}% - ${((8 * (n - 1)) / n).toFixed(1)}px)`, "--lx": n >= 5 ? "30%" : "50%" });
  return (
    <div className="v-fl v-fl-org" style={style}>
      <div className="v-fl-org-root"><Txt path={`${p}.root`} value={b.root} className="v-fl-org-box" max={limits.short} /></div>
      <div className="v-fl-org-bar" aria-hidden="true" />
      <ul className="v-fl-org-branches">
        {b.branches.map((c, i) => (
          <li className="v-fl-org-branch" key={i} data-d={`${p}.branches.${i}`}>
            <Txt path={`${p}.branches.${i}.title`} value={c.title} className="v-fl-org-box" max={limits.short} />
            {c.leaves.length > 0 && (
              <ul className="v-fl-org-leaves">
                {c.leaves.map((l, k) => (
                  <li key={k} data-d={`${p}.branches.${i}.leaves.${k}`}><Txt path={`${p}.branches.${i}.leaves.${k}`} value={l} max={limits.short} /></li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TreeIndent({ b, p, limits }: LookProps<"tree">) {
  const half = Math.ceil(b.branches.length / 2);
  const col = (from: number, to: number) => (
    <ul className="v-fl-tree-l1">
      {b.branches.slice(from, to).map((c, j) => {
        const i = from + j;
        return (
          <li key={i} data-d={`${p}.branches.${i}`}>
            <Txt path={`${p}.branches.${i}.title`} value={c.title} className="v-fl-tree-b" max={limits.short} />
            {c.leaves.length > 0 && (
              <ul className="v-fl-tree-l2">
                {c.leaves.map((l, k) => (
                  <li key={k} data-d={`${p}.branches.${i}.leaves.${k}`}><Txt path={`${p}.branches.${i}.leaves.${k}`} value={l} max={limits.short} /></li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
  return (
    <div className="v-fl v-fl-tree">
      <Txt path={`${p}.root`} value={b.root} as="div" className="v-fl-tree-root" max={limits.short} />
      {b.branches.length > half && <div className="v-fl-tree-bar" aria-hidden="true" />}
      <div className="v-fl-tree-cols">
        <div className="v-fl-tree-c1">{col(0, half)}</div>
        {b.branches.length > half && <div className="v-fl-tree-c2">{col(half, b.branches.length)}</div>}
      </div>
    </div>
  );
}

function TreeNest({ b, p, limits }: LookProps<"tree">) {
  const n = b.branches.length;
  const cols = n <= 2 ? n : n === 4 ? 2 : 3;
  return (
    <div className="v-fl v-fl-nest"><div className="v-fl-nest-outer">
      <Txt path={`${p}.root`} value={b.root} className="v-fl-nest-legend" max={limits.short} />
      <ul className="v-fl-nest-grid" style={vars({ "--c": cols })}>
        {b.branches.map((c, i) => (
          <li className="v-fl-nest-inner" key={i} data-d={`${p}.branches.${i}`}>
            <Txt path={`${p}.branches.${i}.title`} value={c.title} className="v-fl-nest-legend v-fl-nest-sub" max={limits.short} />
            <ul className="v-fl-nest-leaves">
              {c.leaves.map((l, k) => (
                <li key={k} data-d={`${p}.branches.${i}.leaves.${k}`}><Txt path={`${p}.branches.${i}.leaves.${k}`} value={l} max={limits.short} /></li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div></div>
  );
}

function TreeCols({ b, p, limits }: LookProps<"tree">) {
  const n = b.branches.length;
  const phone = n % 2 === 0 ? 2 : 1;
  return (
    <div className="v-fl v-fl-cols">
      <div className="v-fl-cols-root"><Txt path={`${p}.root`} value={b.root} max={limits.short} /></div>
      <ul className={`v-fl-cols-grid${phone === 1 ? " v-fl-cols-one" : ""}`} style={vars({ "--n": n, "--pc": phone })}>
        {b.branches.map((c, i) => (
          <li className="v-fl-cols-col" key={i} data-d={`${p}.branches.${i}`}>
            <Txt path={`${p}.branches.${i}.title`} value={c.title} as="h3" max={limits.short} />
            <ul>
              {c.leaves.map((l, k) => (
                <li key={k} data-d={`${p}.branches.${i}.leaves.${k}`}><Txt path={`${p}.branches.${i}.leaves.${k}`} value={l} max={limits.short} /></li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ---------------- levels ---------------- */

function LevelsCaption({ b, p, limits }: LookProps<"levels">) {
  const { editing } = useContext(EditCtx);
  if (!b.caption && !editing) return null;
  return <figcaption><Txt path={`${p}.caption`} value={b.caption} max={limits.short} /></figcaption>;
}

function LvPyramid(props: LookProps<"levels">) {
  const { b, p, limits } = props;
  const fmt = useNumber();
  const L = b.items, n = L.length, H = 320, bh = H / n, hw = (y: number) => (200 * y) / H;
  return (
    <figure className="v-fl v-fl-py"><div className="v-fl-py-grid">
      <svg className="v-fl-py-svg" viewBox={`0 0 400 ${H}`} aria-hidden="true">
        {L.map((_, i) => {
          const y0 = i ? bh * i + 3 : 0, y1 = bh * (i + 1) - 3;
          return (
            <g key={i}>
              <path className="v-fl-py-band" d={`M${f1(200 - hw(y0))} ${f1(y0)} L${f1(200 + hw(y0))} ${f1(y0)} L${f1(200 + hw(y1))} ${f1(y1)} L${f1(200 - hw(y1))} ${f1(y1)} Z`} />
              <text className="v-fl-py-no" x="200" y={f1((y0 + y1) / 2 + 8)} textAnchor="middle">{fmt(i + 1)}</text>
            </g>
          );
        })}
      </svg>
      <ol className="v-fl-py-rows" style={vars({ "--n": n })}>
        {L.map((l, i) => (
          <li key={i} data-d={`${p}.items.${i}`}>
            <span className="v-fl-py-k">{fmt(i + 1)}</span>
            <Txt path={`${p}.items.${i}.title`} value={l.title} as="h3" max={limits.short} />
            <Txt path={`${p}.items.${i}.text`} value={l.text} as="p" max={limits.item} />
          </li>
        ))}
      </ol>
    </div><LevelsCaption {...props} /></figure>
  );
}

function LvFunnel(props: LookProps<"levels">) {
  const { b, p, limits } = props;
  const fmt = useNumber();
  const L = b.items, n = L.length, top = 240, bh = top / n;
  const xl = (y: number) => 10 + (130 * y) / top, xr = (y: number) => 390 - (130 * y) / top;
  // A title stands in its band when it is narrower than the band at its height, bold letters take about 9.5 units.
  const fit = L.every((l, i) => l.title.length * 9.5 + 24 <= xr(bh * i + bh / 2) - xl(bh * i + bh / 2));
  return (
    <figure className={`v-fl v-fl-fu${fit ? " v-fl-fu-fit" : ""}`}><div className="v-fl-fu-grid">
      <div className="v-fl-box v-fl-fu-box">
        <svg className="v-fl-fu-svg" viewBox="0 0 400 320" aria-hidden="true">
          <path className="v-fl-fu-shape" d={`M10 0 L390 0 L${f1(xr(top))} ${top} L260 318 L140 318 L${f1(xl(top))} ${top} Z`} />
          {L.map((_, i) => {
            const y = bh * (i + 1);
            return (
              <g key={i}>
                <line className="v-fl-fu-div" x1={f1(xl(y))} y1={f1(y)} x2={f1(xr(y))} y2={f1(y)} />
                <text className="v-fl-fu-no" x="200" y={f1(bh * i + bh / 2 + 7)} textAnchor="middle">{fmt(i + 1)}</text>
              </g>
            );
          })}
          <path className="v-fl-fu-arrow" d="M200 262 V300 M188 288 L200 300 L212 288" />
        </svg>
        {L.map((l, i) => (
          <div key={i} className="v-fl-lbl v-fl-fu-lbl" style={{ top: pc(bh * i + bh / 2, 320), left: "50%" }}>
            <Txt path={`${p}.items.${i}.title`} value={l.title} max={limits.short} />
          </div>
        ))}
      </div>
      <ol className="v-fl-fu-rows" style={vars({ "--n": n })}>
        {L.map((l, i) => (
          <li key={i} data-d={`${p}.items.${i}`}>
            <Txt path={`${p}.items.${i}.title`} value={l.title} as="h3" max={limits.short} />
            <Txt path={`${p}.items.${i}.text`} value={l.text} as="p" max={limits.item} />
          </li>
        ))}
      </ol>
    </div><LevelsCaption {...props} /></figure>
  );
}

function LvStair({ b, p, limits }: LookProps<"levels">) {
  const n = Math.max(2, b.items.length);
  const style = vars({ "--o": Math.min(12, 48 / (n - 1)).toFixed(2), "--op": Math.min(8, 32 / (n - 1)).toFixed(2) });
  return (
    <div className="v-fl v-fl-lv"><ol className="v-fl-lv-list" style={style}>
      {b.items.map((l, i) => (
        <li className="v-fl-lv-row" key={i} data-d={`${p}.items.${i}`} style={vars({ "--i": i })}>
          <Txt path={`${p}.items.${i}.title`} value={l.title} className="v-fl-lv-block" max={limits.short} />
          <Txt path={`${p}.items.${i}.text`} value={l.text} as="p" max={limits.item} />
        </li>
      ))}
    </ol></div>
  );
}

const shortTitles = (b: Cycle, max: number) => b.steps.every((s) => s.title.length <= max);

export const LOOKS_FLOW: Looks = {
  steps: [
    { name: "Senkrechte Linie", View: StepsLine },
    { name: "Stepper", fits: (b: Steps) => b.steps.length <= 6, View: StepsStepper },
    { name: "Pfeilkette", fits: (b: Steps) => b.steps.length >= 3 && b.steps.length <= 6, View: StepsChevron },
    { name: "Treppe", View: StepsStair },
    { name: "Große Ziffern", View: StepsBig },
    { name: "Zickzack", View: StepsZig },
    { name: "Nummer und Text", View: StepsIndex },
    { name: "Fluss", View: StepsFlow },
  ],
  cycle: [
    { name: "Ring", fits: (b: Cycle) => b.steps.length === 4 && shortTitles(b, 11), View: CycleRing },
    { name: "Ring und Liste", View: CycleRingList },
    { name: "Kette mit Rückpfeil", View: CycleChain },
    { name: "Donut", View: CycleDonut },
  ],
  timeline: [
    { name: "Senkrecht", View: TlVertical },
    { name: "Waagrecht", fits: (b: Timeline) => b.events.length <= 6, View: TlHorizontal },
    { name: "Wechselseitig", View: TlZig },
    { name: "Meilenstein-Rauten", View: TlDiamond },
    { name: "Große Jahreszahlen", View: TlBig },
  ],
  tree: [
    { name: "Organigramm", View: TreeOrg },
    { name: "Eingerückter Baum", View: TreeIndent },
    { name: "Verschachtelte Rahmen", View: TreeNest },
    { name: "Spalten je Ast", View: TreeCols },
  ],
  levels: [
    { name: "Pyramide", View: LvPyramid },
    { name: "Trichter", View: LvFunnel },
    { name: "Stufen-Treppe", View: LvStair },
  ],
};
