"use client";

import type { ReactNode } from "react";
import type { Block } from "../../_lib/types";
import { useNumber } from "../Charts";
import { Txt } from "../Txt";
import { val } from "./numbers-parts";
import type { Look, LookProps } from "./registry";
import { Caption, DataButton } from "./shared";

type ChartBlock = Extract<Block, { kind: "chart" }>;

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
/** The points of a series in the plot, each in the middle of its category's band. */
function linePoints(b: ChartBlock, s: ChartBlock["series"][number], top: number): number[][] {
  const band = 100 / b.categories.length;
  return b.categories.map((_, i) => [(i + 0.5) * band, 100 - (val(s.values[i]) / top) * 100]);
}

function Legend({ p, limits, series, keyCls }: LookProps<"chart"> & { series: ChartBlock["series"]; keyCls: (k: number) => string }) {
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
  const n = b.categories.length;
  const over: ReactNode[] = [];
  const lines = series.map((s, si) => {
    const pts = linePoints(b, s, sc.top);
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
  const n = b.categories.length;
  const over: ReactNode[] = [];
  const shapes = series.flatMap((s, si) => {
    const pts = linePoints(b, s, sc.top);
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

export const CHART: Look<"chart">[] = [
  { name: "Säulen", View: ChCol },
  { name: "Linie mit Punkten", fits: isLine, View: ChLine },
  { name: "Fläche", fits: isLine, View: ChArea },
  { name: "Donut", fits: (b) => b.chart_type === "pie" && b.categories.length <= 6, View: ChDonut },
  { name: "Waagrechte Balken", fits: (b) => !isLine(b) && b.series.length === 1, View: ChHBar },
  { name: "Punktdiagramm", fits: (b) => isLine(b) && b.series.length === 2, View: ChDots },
];
