"use client";

import { useNumber } from "../Charts";
import { Txt } from "../Txt";
import { Arrow, Dot, Entry, f1, pc, pt } from "./flow-parts";
import type { Look, LookProps } from "./registry";
import { vars } from "./shared";

function CycleRing({ b, p, limits }: LookProps<"cycle">) {
  const fmt = useNumber();
  const S = b.steps, n = S.length, cx = 210, cy = 210, R = 140, span = 360 / n, start = span / 2;
  const arcs = S.map((_, i) => {
    const a = start + span * i, [x1, y1] = pt(cx, cy, R, a + 24), [x2, y2] = pt(cx, cy, R, a + span - 28);
    return `M${f1(x1)} ${f1(y1)} A${R} ${R} 0 0 1 ${f1(x2)} ${f1(y2)}`;
  });
  const nodes = S.map((_, i) => pt(cx, cy, R, start + span * i));
  const marker = `v-fl-ring-m-${p.replace(/\W/g, "-")}`;
  return (
    <div className="v-fl v-fl-ring"><div className="v-fl-ring-grid">
      <div className="v-fl-box v-fl-ring-box">
        <svg className="v-fl-ring-svg" viewBox="0 0 420 420" aria-hidden="true">
          <defs>
            <marker id={marker} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path className="v-fl-ring-head" d="M0 0L10 5L0 10z" />
            </marker>
          </defs>
          {arcs.map((d, i) => <path className="v-fl-ring-arc" key={i} d={d} markerEnd={`url(#${marker})`} />)}
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
              <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
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
            <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
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
              <Entry p={`${p}.steps.${i}`} e={s} limits={limits} />
            </div>
          </li>
        ))}
      </ol>
    </div></div>
  );
}

export const CYCLE: Look<"cycle">[] = [
  { name: "Ring", fits: (b) => b.steps.length === 4 && b.steps.every((s) => s.title.length <= 11), View: CycleRing },
  { name: "Ring und Liste", View: CycleRingList },
  { name: "Kette mit Rückpfeil", View: CycleChain },
  { name: "Donut", View: CycleDonut },
];
