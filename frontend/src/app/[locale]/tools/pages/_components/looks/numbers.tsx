"use client";

import { useContext, type CSSProperties, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import type { Block } from "../../_lib/types";
import { useNumber } from "../Charts";
import { EditCtx, Txt } from "../Txt";
import type { Look, LookProps, Looks } from "./registry";
import { Caption, DataButton, Grow } from "./shared";
import "./numbers.css";

type ChartBlock = Extract<Block, { kind: "chart" }>;

/** A figure's value is a number with its unit, never a sentence. */
const VALUE_MAX = 24;
const vars = (v: Record<string, string | number>) => v as CSSProperties;
const val = (v: number | undefined) => Math.max(0, Number.isFinite(v) ? (v as number) : 0);
const pct = (v: number, max: number) => Math.min(100, Math.max(0, (v / max) * 100));

/* ---------- Kennzahlen ---------- */

function FigItems({ b, p, limits, cls }: LookProps<"figures"> & { cls: string }) {
  return (
    <>
      {b.figures.map((f, i) => (
        <div className={cls} key={i} data-d={`${p}.figures.${i}`}>
          <Txt path={`${p}.figures.${i}.value`} value={f.value} as="strong" max={VALUE_MAX} />
          <Txt path={`${p}.figures.${i}.label`} value={f.label} as="span" max={limits.short} />
        </div>
      ))}
    </>
  );
}

const shortValues = (n: number) => (b: LookProps<"figures">["b"]) => b.figures.every((f) => f.value.length <= n);

function FigRow(x: LookProps<"figures">) {
  return <div className="v-nu-root"><div className="v-nu-fig-row"><FigItems {...x} cls="v-nu-fig-row-it" /></div></div>;
}

function FigSide({ b, p, limits }: LookProps<"figures">) {
  return (
    <div className="v-nu-root">
      <dl className="v-nu-fig-side">
        {b.figures.map((f, i) => (
          <div className="v-nu-fig-side-it" key={i} data-d={`${p}.figures.${i}`}>
            <Txt path={`${p}.figures.${i}.value`} value={f.value} as="dt" max={VALUE_MAX} />
            <Txt path={`${p}.figures.${i}.label`} value={f.label} as="dd" max={limits.short} />
          </div>
        ))}
      </dl>
    </div>
  );
}

function FigHero({ b, p, limits }: LookProps<"figures">) {
  const [h, ...rest] = b.figures;
  return (
    <div className="v-nu-root">
      <div className="v-nu-fig-hero">
        <div className="v-nu-fig-hero-main" data-d={`${p}.figures.0`}>
          <Txt path={`${p}.figures.0.value`} value={h.value} as="strong" max={VALUE_MAX} />
          <Txt path={`${p}.figures.0.label`} value={h.label} as="span" max={limits.short} />
        </div>
        <div className="v-nu-fig-hero-rest">
          {rest.map((f, k) => (
            <div key={k} data-d={`${p}.figures.${k + 1}`}>
              <Txt path={`${p}.figures.${k + 1}.value`} value={f.value} as="strong" max={VALUE_MAX} />
              <Txt path={`${p}.figures.${k + 1}.label`} value={f.label} as="span" max={limits.short} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FigBase(x: LookProps<"figures">) {
  return (
    <div className="v-nu-root">
      <div className="v-nu-fig-base" style={vars({ "--n": x.b.figures.length })}><FigItems {...x} cls="v-nu-fig-base-it" /></div>
    </div>
  );
}

function FigTick(x: LookProps<"figures">) {
  const n = x.b.figures.length;
  // On a phone two columns only when the rows come out full.
  return (
    <div className="v-nu-root">
      <div className="v-nu-fig-tick" style={vars({ "--n": n, "--nc": n % 2 ? 1 : 2 })}><FigItems {...x} cls="v-nu-fig-tick-it" /></div>
    </div>
  );
}

function FigStrip(x: LookProps<"figures">) {
  return (
    <div className="v-nu-root">
      <div className="v-nu-fig-strip" style={vars({ "--n": x.b.figures.length })}><FigItems {...x} cls="v-nu-fig-strip-it" /></div>
    </div>
  );
}

/* ---------- Balken ---------- */

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

/* ---------- Diagramm ---------- */

interface Scale { top: number; ticks: number[] }

/** A round top for the value axis and about five ticks up to it. */
function scaleOf(max: number): Scale {
  const m = max > 0 ? max : 1, raw = m / 5;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 4, 5, 10].map((k) => k * p).find((s) => s >= raw) ?? 10 * p;
  const top = Math.ceil(m / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step / 1000; v += step) ticks.push(Math.round(v * 1000) / 1000);
  return { top, ticks };
}

const drawn = (b: ChartBlock) => (b.chart_type === "pie" ? b.series.slice(0, 1) : b.series.slice(0, 2));
const maxOf = (series: ChartBlock["series"]) => Math.max(0, ...series.flatMap((s) => s.values.map(val)));
const isLine = (b: ChartBlock) => b.chart_type === "line";

function Legend({ b, p, limits, series, keyCls }: LookProps<"chart"> & { series: ChartBlock["series"]; keyCls: (k: number) => string }) {
  if (series.length < 2) return null;
  return (
    <div className="v-nu-ch-leg">
      {series.map((s, k) => (
        <span className="v-nu-ch-key" key={k}><i className={keyCls(k)} /><Txt path={`${p}.series.${k}.name`} value={s.name} max={limits.short} /></span>
      ))}
    </div>
  );
}

interface FrameProps extends LookProps<"chart"> {
  cls: string;
  scale: Scale;
  series: ChartBlock["series"];
  keyCls: (k: number) => string;
  children: ReactNode;
  over?: ReactNode;
}

/** Ticks on the left, categories below, the shapes in a stretched SVG and every label in HTML. */
function VFrame({ cls, scale, series, keyCls, children, over, ...x }: FrameProps) {
  const { b, p, limits, num } = x;
  const fmt = useNumber();
  const n = b.categories.length;
  const ticks = scale.ticks.map((v) => fmt(v));
  const yw = Math.max(44, Math.max(...ticks.map((t) => t.length)) * 8 + 16);
  return (
    <figure className={`v-nu-root has-over${n > 6 ? " v-nu-ch-many" : ""}`}>
      <DataButton p={p} />
      <div className={`v-nu-ch ${cls}`}>
        <Txt path={`${p}.y_label`} value={b.y_label} as="div" className="v-nu-ch-ylab" max={limits.short} />
        <div className="v-nu-ch-frame">
          <div className="v-nu-ch-yax" style={{ width: yw }}>
            {scale.ticks.map((v, k) => <span key={k} style={{ bottom: `${(v / scale.top) * 100}%` }}>{ticks[k]}</span>)}
          </div>
          <div className="v-nu-ch-plot">
            <svg className="v-nu-ch-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              {scale.ticks.filter((v) => v > 0).map((v) => {
                const y = 100 - (v / scale.top) * 100;
                return <line key={v} className="v-nu-ch-grid" x1={0} x2={100} y1={y} y2={y} vectorEffect="non-scaling-stroke" />;
              })}
              {children}
            </svg>
            {over}
          </div>
          <div className="v-nu-ch-xax" style={{ gridTemplateColumns: `repeat(${n}, 1fr)` }}>
            {b.categories.map((c, i) => (
              <span key={i}>
                <span className="v-nu-ch-xno">{i + 1}</span>
                <Txt path={`${p}.categories.${i}`} value={c} className="v-nu-ch-xname" max={limits.label} />
              </span>
            ))}
          </div>
          <Txt path={`${p}.x_label`} value={b.x_label} as="div" className="v-nu-ch-xlab" max={limits.short} />
        </div>
        {n > 6 && (
          // Many categories get numbers on a phone, the names follow in this key.
          <ol className="v-nu-ch-xkey">
            {b.categories.map((c, i) => <li key={i}><Txt path={`${p}.categories.${i}`} value={c} max={limits.label} /></li>)}
          </ol>
        )}
        <Legend {...x} series={series} keyCls={keyCls} />
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

/** Categories as rows on the left, the value axis below. */
function HFrame({ cls, scale, series, keyCls, children, over, rowH, ...x }: FrameProps & { rowH: number }) {
  const { b, p, limits, num } = x;
  const fmt = useNumber();
  const n = b.categories.length;
  return (
    <figure className="v-nu-root has-over">
      <DataButton p={p} />
      <div className={`v-nu-ch ${cls}`}>
        <div className="v-nu-ch-hframe">
          <div className="v-nu-ch-rows" style={{ gridTemplateRows: `repeat(${n}, 1fr)` }}>
            {b.categories.map((c, i) => <span key={i}><Txt path={`${p}.categories.${i}`} value={c} max={limits.label} /></span>)}
          </div>
          <div className="v-nu-ch-plot v-nu-ch-hplot" style={{ height: n * rowH }}>
            <svg className="v-nu-ch-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              {scale.ticks.filter((v) => v > 0).map((v) => {
                const gx = (v / scale.top) * 100;
                return <line key={v} className="v-nu-ch-grid" x1={gx} x2={gx} y1={0} y2={100} vectorEffect="non-scaling-stroke" />;
              })}
              {children}
            </svg>
            {over}
          </div>
          <div className="v-nu-ch-xticks">
            {scale.ticks.map((v) => <span key={v} style={{ left: `${(v / scale.top) * 100}%` }}>{fmt(v)}</span>)}
          </div>
          <Txt path={`${p}.y_label`} value={b.y_label} as="div" className="v-nu-ch-xlab" max={limits.short} />
        </div>
        <Legend {...x} series={series} keyCls={keyCls} />
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

const tip = (s: ChartBlock["series"][number], many: boolean, c: string, v: string) => `${many && s.name ? `${s.name}, ` : ""}${c}: ${v}`;

function ChCol(x: LookProps<"chart">) {
  const { b } = x, fmt = useNumber();
  const series = drawn(b), sc = scaleOf(maxOf(series));
  const n = b.categories.length, band = 100 / n, k = series.length;
  const w = band * 0.2, g = band * 0.05, span = k * w + (k - 1) * g;
  const over: ReactNode[] = [];
  const rects = series.flatMap((s, si) => b.categories.map((c, i) => {
    const v = val(s.values[i]), h = (v / sc.top) * 100, bx = (i + 0.5) * band - span / 2 + si * (w + g);
    if (i === n - 1) over.push(<span key={si} className="v-nu-ch-val" style={{ left: `${bx + w / 2}%`, bottom: `${h}%` }}>{fmt(v)}</span>);
    return (
      <rect key={`${si}-${i}`} className={`v-nu-f${si + 1}`} x={bx} y={100 - h} width={w} height={h}>
        <title>{tip(s, k > 1, c, fmt(v))}</title>
      </rect>
    );
  }));
  return <VFrame {...x} cls="v-nu-ch-col" scale={sc} series={series} keyCls={(j) => `v-nu-k${j + 1}`} over={over}>{rects}</VFrame>;
}

function ChLine(x: LookProps<"chart">) {
  const { b } = x, fmt = useNumber();
  const series = drawn(b), sc = scaleOf(maxOf(series));
  const n = b.categories.length, band = 100 / n;
  const over: ReactNode[] = [];
  const lines = series.map((s, si) => {
    const pts = b.categories.map((_, i) => [(i + 0.5) * band, 100 - (val(s.values[i]) / sc.top) * 100]);
    pts.forEach((pt, i) => over.push(
      <i key={`${si}-${i}`} className={`v-nu-dot v-nu-k${si + 1}`} style={{ left: `${pt[0]}%`, top: `${pt[1]}%` }} title={tip(s, series.length > 1, b.categories[i], fmt(val(s.values[i])))} />,
    ));
    const e = pts[n - 1];
    over.push(<span key={`e${si}`} className="v-nu-ch-end" style={{ left: `${e[0]}%`, top: `${e[1]}%` }}>{fmt(val(s.values[n - 1]))}</span>);
    return <polyline key={si} className={`v-nu-l${si + 1}`} points={pts.map((pt) => pt.join(",")).join(" ")} vectorEffect="non-scaling-stroke" />;
  });
  return <VFrame {...x} cls="v-nu-ch-line" scale={sc} series={series} keyCls={(j) => `v-nu-k${j + 1} v-nu-ln`} over={over}>{lines}</VFrame>;
}

function ChArea(x: LookProps<"chart">) {
  const { b } = x, fmt = useNumber();
  const series = drawn(b), sc = scaleOf(maxOf(series));
  const n = b.categories.length, band = 100 / n;
  const over: ReactNode[] = [];
  const shapes = series.flatMap((s, si) => {
    const pts = b.categories.map((_, i) => [(i + 0.5) * band, 100 - (val(s.values[i]) / sc.top) * 100]);
    const line = pts.map((pt) => pt.join(",")).join(" ");
    const e = pts[n - 1];
    over.push(
      <i key={`d${si}`} className={`v-nu-dot v-nu-k${si + 1}`} style={{ left: `${e[0]}%`, top: `${e[1]}%` }} />,
      <span key={`e${si}`} className="v-nu-ch-end" style={{ left: `${e[0]}%`, top: `${e[1]}%` }}>{fmt(val(s.values[n - 1]))}</span>,
    );
    const out = [<polyline key={`l${si}`} className={`v-nu-l${si + 1}`} points={line} vectorEffect="non-scaling-stroke" />];
    if (si === 0) out.unshift(<polygon key="a" className="v-nu-a1" points={`${line} ${e[0]},100 ${pts[0][0]},100`} />);
    return out;
  });
  return <VFrame {...x} cls="v-nu-ch-area" scale={sc} series={series} keyCls={(j) => (j ? `v-nu-k${j + 1} v-nu-ln` : "v-nu-ka1")} over={over}>{shapes}</VFrame>;
}

function ChDonut({ b, p, limits, num }: LookProps<"chart">) {
  const fmt = useNumber();
  const vals = b.categories.map((_, i) => val(b.series[0]?.values[i]));
  const total = vals.reduce((s, v) => s + v, 0) || 1;
  const share = (i: number) => `${fmt(Math.round((vals[i] / total) * 100))} %`;
  const gap = 0.6;
  let start = 0;
  const segs = vals.map((v, i) => {
    const s = (v / total) * 100;
    const el = (
      <circle key={i} className={`v-nu-dn-seg v-nu-c${i + 1}`} cx={60} cy={60} r={44} pathLength={100}
        strokeDasharray={`${Math.max(0, s - gap)} ${100 - s + gap}`} strokeDashoffset={-(start + gap / 2)}>
        <title>{`${b.categories[i]}: ${share(i)}`}</title>
      </circle>
    );
    start += s;
    return el;
  });
  const big = vals.indexOf(Math.max(...vals));
  return (
    <figure className="v-nu-root has-over">
      <DataButton p={p} />
      <div className="v-nu-ch v-nu-ch-donut">
        <div className="v-nu-dn-wrap">
          <div className="v-nu-dn-ring">
            <svg className="v-nu-dn-svg" viewBox="0 0 120 120" role="img" aria-label={b.caption}><g transform="rotate(-90 60 60)">{segs}</g></svg>
            <div className="v-nu-dn-center">
              <strong>{share(big)}</strong>
              <Txt path={`${p}.categories.${big}`} value={b.categories[big]} max={limits.label} />
            </div>
          </div>
          <ul className="v-nu-dn-list">
            {b.categories.map((c, i) => (
              <li key={i}><i className={`v-nu-dn-sw v-nu-c${i + 1}`} /><span><Txt path={`${p}.categories.${i}`} value={c} max={limits.label} /></span><b>{share(i)}</b></li>
            ))}
          </ul>
        </div>
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

function ChHBar(x: LookProps<"chart">) {
  const { b } = x, fmt = useNumber();
  const series = b.series.slice(0, 1), sc = scaleOf(maxOf(series));
  const n = b.categories.length, band = 100 / n, t = band * 0.5;
  const over: ReactNode[] = [];
  const rects = b.categories.map((c, i) => {
    const v = val(series[0]?.values[i]), w = (v / sc.top) * 100, y = (i + 0.5) * band;
    over.push(<span key={i} className="v-nu-ch-tip" style={{ left: `${w}%`, top: `${y}%` }}>{fmt(v)}</span>);
    return <rect key={i} className="v-nu-f1" x={0} y={y - t / 2} width={w} height={t}><title>{`${c}: ${fmt(v)}`}</title></rect>;
  });
  return <HFrame {...x} cls="v-nu-ch-hbar" scale={sc} series={series} keyCls={() => "v-nu-k1"} rowH={44} over={over}>{rects}</HFrame>;
}

function ChDots(x: LookProps<"chart">) {
  const { b } = x, fmt = useNumber();
  const series = b.series.slice(0, 2), sc = scaleOf(maxOf(series));
  const n = b.categories.length, band = 100 / n;
  const over: ReactNode[] = [];
  const cons = b.categories.map((c, i) => {
    const y = (i + 0.5) * band, xs = series.map((s) => (val(s.values[i]) / sc.top) * 100);
    series.forEach((s, si) => {
      over.push(<i key={`${si}-${i}`} className={`v-nu-dot v-nu-k${si + 1}`} style={{ left: `${xs[si]}%`, top: `${y}%` }} title={tip(s, true, c, fmt(val(s.values[i])))} />);
      if (i === n - 1) over.push(<span key={`v${si}`} className="v-nu-ch-val v-nu-ch-above" style={{ left: `${xs[si]}%`, top: `${y}%` }}>{fmt(val(s.values[i]))}</span>);
    });
    return <line key={i} className="v-nu-ch-con" x1={Math.min(...xs)} x2={Math.max(...xs)} y1={y} y2={y} vectorEffect="non-scaling-stroke" />;
  });
  return <HFrame {...x} cls="v-nu-ch-dots" scale={sc} series={series} keyCls={(j) => `v-nu-k${j + 1} v-nu-rd`} rowH={40} over={over}>{cons}</HFrame>;
}

/* ---------- Tabelle ---------- */

type CellRender = (c: string, j: number, txt: ReactNode) => ReactNode;

function TableLook({ b, p, limits, num, cls, cell }: LookProps<"table"> & { cls: string; cell?: CellRender }) {
  const t = useTranslations("tools.pages");
  const S = limits.short;
  // A row head column of short entries stays on one line and takes only its own width.
  const tight = b.rows.every((r) => (r[0] ?? "").length <= 24);
  return (
    <figure className="v-nu-root">
      <div className={`v-nu-tb ${cls}${tight ? " v-nu-tb-tight" : ""}`}>
        <table>
          <thead>
            <tr>{b.header.map((h, i) => <th key={i} scope="col"><Txt path={`${p}.header.${i}`} value={h} as="div" max={S} keep /></th>)}</tr>
          </thead>
          <tbody>
            {b.rows.map((r, i) => (
              <tr key={i} data-d={`${p}.rows.${i}`}>
                {r.map((c, j) => {
                  const txt = <Txt path={`${p}.rows.${i}.${j}`} value={c} as="div" max={S} keep />;
                  return j === 0
                    ? <th key={j} scope="row" data-h={b.header[0]}>{txt}</th>
                    : <td key={j} data-h={b.header[j]}>{cell ? cell(c, j, txt) : txt}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <Grow items={[
          { what: "row", path: p, full: b.rows.length >= limits.tableRows, label: t("addRow"), limit: t("maxRows", { max: limits.tableRows }) },
          { what: "col", path: p, full: b.header.length >= limits.tableCols, label: t("addCol"), limit: t("maxCols", { max: limits.tableCols }) },
        ]} />
      </div>
      <Caption p={p} b={b} num={num} kind="table" limits={limits} />
    </figure>
  );
}

/** A whole number from 0 to 10 in a cell, any other text gives null. */
const smallInt = (s: string) => (/^\s*(10|\d)\s*$/.test(s) ? Number(s) : null);

/** The columns after the first whose cells are all small whole numbers, with the steps of their scale. */
function ratedColumns(b: LookProps<"table">["b"]): (number | null)[] {
  return b.header.map((_, j) => {
    if (j === 0 || b.rows.length < 2) return null;
    const nums = b.rows.map((r) => smallInt(r[j] ?? ""));
    if (nums.some((v) => v === null)) return null;
    const max = Math.max(...nums.map((v) => v ?? 0));
    return max >= 1 ? (max <= 5 ? 5 : 10) : null;
  });
}

const TbPlain = (x: LookProps<"table">) => <TableLook {...x} cls="v-nu-tb-plain" />;
const TbStripe = (x: LookProps<"table">) => <TableLook {...x} cls="v-nu-tb-stripe" />;

function TbDots(x: LookProps<"table">) {
  const rated = ratedColumns(x.b);
  const cell: CellRender = (c, j, txt) => {
    const steps = rated[j];
    if (!steps) return txt;
    const v = smallInt(c) ?? 0;
    return (
      <span className="v-nu-tb-rate">
        <span className="v-nu-tb-lv" role="img" aria-label={c}>
          {Array.from({ length: steps }, (_, k) => <i key={k} className={k < v ? "v-nu-on" : "v-nu-off"} />)}
        </span>
        <span className="v-nu-tb-word">{txt}</span>
      </span>
    );
  };
  return <TableLook {...x} cls="v-nu-tb-dots" cell={cell} />;
}

/* ---------- Skala ---------- */

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
  const { editing } = useContext(EditCtx);
  return (
    <figure className="v-nu-root">
      <div className={cls} style={vars({ "--nh": `${Math.max(280, b.items.length * 60)}px` })}>
        <Txt path={`${p}.left`} value={b.left} className="v-nu-sc-pole" max={limits.short} />
        {children}
        <Txt path={`${p}.right`} value={b.right} className="v-nu-sc-pole" max={limits.short} />
      </div>
      {(b.caption || editing) && <figcaption><Txt path={`${p}.caption`} value={b.caption} max={limits.short} /></figcaption>}
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

/* ---------- Register ---------- */

const figures: Look<"figures">[] = [
  { name: "Reihe mit Trennstrichen", fits: shortValues(14), View: FigRow },
  { name: "Zahl links, Text rechts", View: FigSide },
  { name: "Hauptzahl mit Nebenzahlen", fits: (b) => b.figures.length >= 2 && b.figures[0].value.length <= 12 && shortValues(20)(b), View: FigHero },
  { name: "Zahlen auf Grundlinie", fits: shortValues(14), View: FigBase },
  { name: "Akzentstrich darüber", fits: shortValues(20), View: FigTick },
  { name: "Köpfe einer Leiste", fits: shortValues(16), View: FigStrip },
];

const bars: Look<"bars">[] = [
  { name: "Waagrechte Balken", View: BarH },
  { name: "Lollipop", View: BarLolli },
  { name: "Rangliste", View: BarRank },
  { name: "Prozent-Waffel", fits: percentBars, View: BarWaffle },
  { name: "Beschriftung im Balken", fits: (b) => b.bars.every((x) => x.label.length <= 28), View: BarIn },
];

const chart: Look<"chart">[] = [
  { name: "Säulen", View: ChCol },
  { name: "Linie mit Punkten", fits: isLine, View: ChLine },
  { name: "Fläche", fits: isLine, View: ChArea },
  { name: "Donut", fits: (b) => b.chart_type === "pie" && b.categories.length <= 6, View: ChDonut },
  { name: "Waagrechte Balken", fits: (b) => !isLine(b) && b.series.length === 1, View: ChHBar },
  { name: "Punktdiagramm", fits: (b) => isLine(b) && b.series.length === 2, View: ChDots },
];

const table: Look<"table">[] = [
  { name: "Schlicht mit Kopflinie", View: TbPlain },
  { name: "Gestreift", View: TbStripe },
  { name: "Bewertung mit Punkten", fits: (b) => ratedColumns(b).some(Boolean), View: TbDots },
];

const scale: Look<"scale">[] = [
  { name: "Linie zwischen Polen", fits: (b) => b.items.length <= 6 && shortLabels(b) && minGap(b, 1) >= 0.14, View: ScLine },
  { name: "Abschnittsband", View: ScBand },
  { name: "Regler-Punkte", fits: (b) => b.items.length <= 8 && shortLabels(b) && minGap(b, 2) >= 0.14, View: ScAlt },
];

export const LOOKS_NUMBERS: Looks = { figures, bars, chart, table, scale };
