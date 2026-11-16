"use client";

import { useNumber } from "../Charts";
import { Txt } from "../Txt";
import { Entry, f1, pc } from "./flow-parts";
import type { Look, LookProps } from "./registry";
import { PlainCaption, vars } from "./shared";

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
            <Entry p={`${p}.items.${i}`} e={l} limits={limits} />
          </li>
        ))}
      </ol>
    </div><PlainCaption {...props} /></figure>
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
            <Entry p={`${p}.items.${i}`} e={l} limits={limits} />
          </li>
        ))}
      </ol>
    </div><PlainCaption {...props} /></figure>
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

export const LEVELS: Look<"levels">[] = [
  { name: "Pyramide", View: LvPyramid },
  { name: "Trichter", View: LvFunnel },
  { name: "Stufen-Treppe", View: LvStair },
];
