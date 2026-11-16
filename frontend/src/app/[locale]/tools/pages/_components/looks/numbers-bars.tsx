"use client";

import { useNumber } from "../Charts";
import { Txt } from "../Txt";
import { val } from "./numbers-parts";
import type { Look, LookProps } from "./registry";
import { DataButton, vars } from "./shared";

const pct = (v: number, max: number) => Math.min(100, Math.max(0, (v / max) * 100));
const barMax = (b: LookProps<"bars">["b"]) => b.max || Math.max(...b.bars.map((x) => val(x.value))) || 1;

function BarLabel({ b, p, limits, i, cls }: LookProps<"bars"> & { i: number; cls: string }) {
  return (
    <div className={cls}>
      <Txt path={`${p}.bars.${i}.label`} value={b.bars[i].label} as="b" max={limits.short} />
      <Txt path={`${p}.bars.${i}.text`} value={b.bars[i].text} as="span" max={limits.item} />
    </div>
  );
}

function BarH(x: LookProps<"bars">) {
  const { b, p } = x, fmt = useNumber(), max = barMax(b);
  return (
    <div className="v-nu-root has-over">
      <DataButton p={p} />
      <div className="v-nu-bar-h">
        {b.bars.map((it, i) => (
          <div className="v-nu-bar-h-row" key={i} data-d={`${p}.bars.${i}`}>
            <BarLabel {...x} i={i} cls="v-nu-bar-h-lab" />
            <div className="v-nu-bar-h-track"><i style={{ width: `${pct(val(it.value), max)}%` }} /></div>
            <div className="v-nu-bar-h-val">{fmt(val(it.value))}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BarLolli(x: LookProps<"bars">) {
  const { b, p } = x, fmt = useNumber(), max = barMax(b);
  return (
    <div className="v-nu-root has-over">
      <DataButton p={p} />
      <div className="v-nu-bar-lolli">
        {b.bars.map((it, i) => {
          const w = pct(val(it.value), max);
          return (
            <div className="v-nu-bar-lolli-row" key={i} data-d={`${p}.bars.${i}`}>
              <BarLabel {...x} i={i} cls="v-nu-bar-lolli-lab" />
              <div className="v-nu-bar-lolli-track">
                <i className="v-nu-bar-lolli-stem" style={{ width: `${w}%` }} />
                <i className="v-nu-bar-lolli-dot" style={{ left: `${w}%` }} />
                <em className={`v-nu-bar-lolli-val${w > 85 ? " v-nu-bar-lolli-in" : ""}`} style={{ left: `${w}%` }}>{fmt(val(it.value))}</em>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BarRank(x: LookProps<"bars">) {
  const { b, p } = x, fmt = useNumber(), max = barMax(b);
  const order = b.bars.map((it, i) => ({ it, i })).sort((u, v) => val(v.it.value) - val(u.it.value));
  return (
    <div className="v-nu-root has-over">
      <DataButton p={p} />
      <ol className="v-nu-bar-rank">
        {order.map(({ it, i }, r) => (
          <li key={i} data-d={`${p}.bars.${i}`}>
            <span className="v-nu-bar-rank-no">{r + 1}</span>
            <BarLabel {...x} i={i} cls="v-nu-bar-rank-lab" />
            <span className="v-nu-bar-rank-val">{fmt(val(it.value))}</span>
            <span className="v-nu-bar-rank-line"><i style={{ width: `${pct(val(it.value), max)}%` }} /></span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** The waffle counts hundredths, so the values must be shares of a hundred. */
const percentBars = (b: LookProps<"bars">["b"]) =>
  (b.max ?? 100) === 100 && b.bars.length <= 5 && b.bars.every((x) => x.value >= 0 && x.value <= 100);

function BarWaffle({ b, p, limits }: LookProps<"bars">) {
  const fmt = useNumber();
  return (
    <div className="v-nu-root has-over">
      <DataButton p={p} />
      <div className="v-nu-bar-waffle" style={vars({ "--n": b.bars.length })}>
        {b.bars.map((it, i) => {
          const on = Math.round(pct(val(it.value), 100));
          return (
            <div className="v-nu-bar-waffle-it" key={i} data-d={`${p}.bars.${i}`}>
              <svg viewBox="0 0 100 100" className="v-nu-bar-waffle-svg" role="img" aria-label={fmt(val(it.value))}>
                {Array.from({ length: 100 }, (_, k) => (
                  <rect key={k} x={(k % 10) * 10 + 1} y={(9 - Math.floor(k / 10)) * 10 + 1} width={8} height={8} className={k < on ? "v-nu-on" : "v-nu-off"} />
                ))}
              </svg>
              <div className="v-nu-bar-waffle-txt">
                <strong>{fmt(val(it.value))}</strong>
                <Txt path={`${p}.bars.${i}.label`} value={it.label} as="b" max={limits.short} />
                <Txt path={`${p}.bars.${i}.text`} value={it.text} as="span" max={limits.item} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BarIn({ b, p, limits }: LookProps<"bars">) {
  const fmt = useNumber(), max = barMax(b);
  return (
    <div className="v-nu-root has-over">
      <DataButton p={p} />
      <div className="v-nu-bar-in">
        {b.bars.map((it, i) => {
          const w = pct(val(it.value), max), inside = w >= 45;
          return (
            <div className="v-nu-bar-in-row" key={i} data-d={`${p}.bars.${i}`} style={vars({ "--w": `${w}%` })}>
              <Txt path={`${p}.bars.${i}.label`} value={it.label} as="b" className={`v-nu-bar-in-lab${inside ? "" : " v-nu-bar-in-out"}`} max={limits.short} />
              <div className="v-nu-bar-in-bar">
                <i />
                <em className={`v-nu-bar-in-val${w >= 88 ? " v-nu-bar-in-white" : ""}`}>{fmt(val(it.value))}</em>
              </div>
              <Txt path={`${p}.bars.${i}.text`} value={it.text} as="span" className="v-nu-bar-in-text" max={limits.item} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export const BARS: Look<"bars">[] = [
  { name: "Waagrechte Balken", View: BarH },
  { name: "Lollipop", View: BarLolli },
  { name: "Rangliste", View: BarRank },
  { name: "Prozent-Waffel", fits: percentBars, View: BarWaffle },
  { name: "Beschriftung im Balken", fits: (b) => b.bars.every((x) => x.label.length <= 28), View: BarIn },
];
