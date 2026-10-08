"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import type { Block } from "../_lib/types";

type ChartBlock = Extract<Block, { kind: "chart" }>;
type MindBlock = Extract<Block, { kind: "mindmap" }>;
type CloudBlock = Extract<Block, { kind: "wordcloud" }>;

/** A number as the page's readers write it, comma or point. */
export function useNumber() {
  const locale = useLocale();
  return (v: number, digits?: number) =>
    new Intl.NumberFormat(locale, digits == null ? { maximumFractionDigits: 2 } : {
      minimumFractionDigits: digits, maximumFractionDigits: digits,
    }).format(v);
}

/** A tidy top for the value axis just above the largest value, divisible into four steps. */
function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const step = [1, 1.2, 1.6, 2, 2.4, 3, 4, 5, 6, 8, 10].find((m) => m * p >= v) ?? 10;
  return step * p;
}

export function Chart({ b }: { b: ChartBlock }) {
  const num = useNumber();
  // The point or bar under the pointer, its value shows in a small box above it.
  const [hover, setHover] = useState<{ s: number; i: number } | null>(null);
  // In a narrow field the drawing shrinks, its letters grow by this factor to stay readable.
  const ref = useRef<SVGSVGElement>(null);
  const [f, setF] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fit = () => setF(Math.min(2.2, Math.max(1, 1000 / (el.clientWidth || 1000))));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const W = 1000, H = 380 + 60 * (f - 1), L = 64 * f, R = 20, T0 = 30 * f, B = 56 * f;
  const n = b.categories.length;
  const max = niceMax(Math.max(...b.series.flatMap((s) => s.values)));
  const sx = (i: number) => L + (n === 1 ? 0.5 : i / (n - 1)) * (W - L - R);
  const sy = (v: number) => H - B - (v / max) * (H - T0 - B);
  const bw = (W - L - R) / n;
  const bar = b.chart_type === "bar";
  const at = (s: number, i: number) => ({
    x: bar ? L + i * bw + bw / 2 : sx(i),
    y: sy(b.series[s].values[i]),
  });
  const tip = (s: number, i: number) => {
    const name = b.series.length > 1 && b.series[s].name ? `${b.series[s].name}: ` : "";
    return { head: b.x_label ? `${b.x_label}: ${b.categories[i]}` : b.categories[i], value: `${name}${num(b.series[s].values[i])}${b.y_label ? ` ${b.y_label}` : ""}` };
  };
  const show = (s: number, i: number) => ({
    onMouseEnter: () => setHover({ s, i }),
    onMouseLeave: () => setHover(null),
    onClick: () => setHover((h) => (h && h.s === s && h.i === i ? null : { s, i })),
  });

  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={b.caption} className="chart">
      {[0, 1, 2, 3, 4].map((k) => {
        const v = (max * k) / 4, y = sy(v);
        return (
          <g key={k}>
            <line className="grid-line" x1={L} x2={W - R} y1={y} y2={y} strokeWidth={2} />
            <text className="axis" x={L - 10} y={y + 5 * f} textAnchor="end" fontSize={14 * f}>{num(v)}</text>
          </g>
        );
      })}
      {bar
        ? b.series[0].values.map((v, i) => {
            const h = (v / max) * (H - T0 - B);
            return (
              <rect key={i} className={`bar${hover?.i === i ? " on" : ""}`} x={L + i * bw + bw * 0.2} y={H - B - h}
                width={bw * 0.6} height={Math.max(h, 1)} rx={6} {...show(0, i)}>
                <title>{`${b.categories[i]}: ${num(v)}`}</title>
              </rect>
            );
          })
        : b.series.map((s, k) => (
            <g key={k}>
              <polyline className={`s${k}`} fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round"
                strokeDasharray={k ? "10 8" : undefined} points={s.values.map((v, i) => `${sx(i)},${sy(v)}`).join(" ")} />
              {!k && s.values.map((v, i) => <circle key={i} className="dot" cx={sx(i)} cy={sy(v)} r={7} strokeWidth={3} />)}
              {/* Wide invisible targets, a line is hard to hit with the pointer. */}
              {s.values.map((v, i) => (
                <circle key={`h${i}`} className="hit" cx={sx(i)} cy={sy(v)} r={18} {...show(k, i)}>
                  <title>{`${b.categories[i]}: ${num(v)}`}</title>
                </circle>
              ))}
            </g>
          ))}
      {b.categories.map((c, i) => (
        <text key={i} className="axis" x={bar ? L + i * bw + bw / 2 : sx(i)} y={H - B + 24 * f} textAnchor="middle" fontSize={14 * f}>{c}</text>
      ))}
      {b.x_label && <text className="axis-title" x={W - R} y={H - 8} textAnchor="end" fontSize={14 * f}>{b.x_label}</text>}
      {b.y_label && <text className="axis-title" x={L} y={T0 - 10} fontSize={14 * f}>{b.y_label}</text>}
      {hover && (() => {
        const p = at(hover.s, hover.i), tx = tip(hover.s, hover.i);
        const w = (Math.max(tx.head.length, tx.value.length) * 8.6 + 28) * f, h = 52 * f;
        const x = Math.min(Math.max(p.x - w / 2, L), W - R - w);
        const y = Math.max(p.y - h - 16, 4);
        return (
          <g className="tip" pointerEvents="none">
            {!bar && <circle className="tip-ring" cx={p.x} cy={p.y} r={11} strokeWidth={3} />}
            <rect x={x} y={y} width={w} height={h} rx={10} />
            <text x={x + 14 * f} y={y + 21 * f} fontSize={13 * f} className="tip-head">{tx.head}</text>
            <text x={x + 14 * f} y={y + 41 * f} fontSize={16 * f} className="tip-value">{tx.value}</text>
          </g>
        );
      })()}
    </svg>
  );
}

const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);

/** A label on one line, or broken into two at the word nearest the middle, each line cut to its room. */
function lines(s: string, room: number): string[] {
  if (s.length <= room) return [s];
  const words = s.split(" ");
  let best = 1, gap = Infinity;
  for (let k = 1; k < words.length; k++) {
    const d = Math.abs(words.slice(0, k).join(" ").length - words.slice(k).join(" ").length);
    if (d < gap) { gap = d; best = k; }
  }
  if (words.length < 2) return [cut(s, room)];
  return [cut(words.slice(0, best).join(" "), room), cut(words.slice(best).join(" "), room)];
}

/** Text lines centred on y, as many tspans as there are lines. */
function Lines({ x, y, list, lh, ...rest }: { x: number; y: number; list: string[]; lh: number } & React.SVGProps<SVGTextElement>) {
  const top = y - ((list.length - 1) * lh) / 2;
  return (
    <text x={x} {...rest}>
      {list.map((l, k) => <tspan key={k} x={x} y={top + k * lh}>{l}</tspan>)}
    </text>
  );
}

/** The page's sections around its title, right side top to bottom, then the left side back up. */
export function MindMap({ b }: { b: MindBlock }) {
  const t = useTranslations("tools.pages");
  const W = 1280, CX = 640, NODE_DX = 250, LEAF_LINE = 19, LEAF_GAP = 14;
  const n = b.branches.length;
  const right = b.branches.slice(0, Math.ceil(n / 2));
  const left = b.branches.slice(Math.ceil(n / 2)).reverse();
  // Every label may take two lines, the room of a line follows the place it has.
  const leafLines = (br: MindBlock["branches"][number]) => br.leaves.map((l) => lines(l, 24));
  const leafHeight = (br: MindBlock["branches"][number]) =>
    leafLines(br).reduce((a, ls) => a + ls.length * LEAF_LINE + LEAF_GAP, -LEAF_GAP);
  const slot = (br: MindBlock["branches"][number]) => Math.max(80, leafHeight(br) + 28);
  const H = Math.max(280, Math.max(right.reduce((a, br) => a + slot(br), 0), left.reduce((a, br) => a + slot(br), 0)) + 60);
  const CY = H / 2;
  const go = (to: string) => {
    const el = to ? document.getElementById(to) : null;
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  const side = (list: MindBlock["branches"], dir: 1 | -1) => {
    let y = (H - list.reduce((a, br) => a + slot(br), 0)) / 2;
    return list.map((br, k) => {
      const ny = y + slot(br) / 2;
      y += slot(br);
      const title = lines(br.title, 20);
      const longest = Math.max(...title.map((l) => l.length));
      const hw = Math.min(118, Math.max(56, longest * 4.7 + 24));
      const hh = title.length > 1 ? 32 : 22;
      const nodeX = CX + dir * NODE_DX;
      const mx = (CX + nodeX) / 2;
      const ex = nodeX + dir * hw, dx = nodeX + dir * (hw + 40);
      const ll = leafLines(br);
      let ly0 = ny - leafHeight(br) / 2;
      return (
        <g key={`${dir}${k}`} className="mm-br" tabIndex={0} role="link" aria-label={t("jumpTo", { title: br.title })}
          onClick={() => go(br.to)} onKeyDown={(e) => { if (e.key === "Enter") go(br.to); }}>
          <path className="mm-edge" d={`M${CX},${CY} C${mx},${CY} ${mx},${ny} ${nodeX},${ny}`} strokeWidth={5} strokeLinecap="round" />
          {ll.map((ls, i) => {
            const h = ls.length * LEAF_LINE;
            const ly = ly0 + h / 2;
            ly0 += h + LEAF_GAP;
            return (
              <g key={i}>
                <path className="mm-edge" d={`M${ex},${ny} C${(ex + dx) / 2},${ny} ${(ex + dx) / 2},${ly} ${dx},${ly}`} strokeWidth={2.5} />
                <circle className="mm-leaf-dot" cx={dx} cy={ly} r={4.5} />
                <Lines className="mm-leaf" x={dx + dir * 12} y={ly + 5} list={ls} lh={LEAF_LINE} textAnchor={dir < 0 ? "end" : "start"} fontSize={15} />
              </g>
            );
          })}
          <rect className="mm-node" x={nodeX - hw} y={ny - hh} width={hw * 2} height={hh * 2} rx={22} strokeWidth={3} />
          <Lines className="mm-node-text" x={nodeX} y={ny + 6} list={title} lh={19} textAnchor="middle" fontSize={16} />
        </g>
      );
    });
  };

  const center = lines(b.center, 20);
  const cw = Math.min(250, Math.max(...center.map((l) => l.length)) * 11 + 48);
  const ch = center.length > 1 ? 40 : 28;
  return (
    <svg className="mm-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("mindmapAria")}>
      {side(right, 1)}
      {side(left, -1)}
      <rect className="mm-center" x={CX - cw / 2} y={CY - ch} width={cw} height={ch * 2} rx={28} />
      <Lines className="mm-center-text" x={CX} y={CY + 7} list={center} lh={23} textAnchor="middle" fontSize={20} />
    </svg>
  );
}

/** The words placed on a spiral from the middle out, the most frequent first and largest. */
export function WordCloud({ b }: { b: CloudBlock }) {
  const t = useTranslations("tools.pages");
  const ref = useRef<SVGSVGElement>(null);

  useLayoutEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    const draw = () => {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      const narrow = svg.getBoundingClientRect().width < 620;
      const W = narrow ? 560 : 1000, H = narrow ? 520 : 400;
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      const ws = b.words;
      const max = ws[0][1], min = ws[ws.length - 1][1];
      const size = (n: number) => 16 + Math.sqrt((n - min) / (max - min || 1)) * 50;
      const placed: { x: number; y: number; w: number; h: number }[] = [];
      const hit = (r: { x: number; y: number; w: number; h: number }) =>
        placed.some((p) => r.x < p.x + p.w + 8 && r.x + r.w + 8 > p.x && r.y < p.y + p.h + 3 && r.y + r.h + 3 > p.y);
      ws.forEach(([w, n], i) => {
        const el = document.createElementNS("http://www.w3.org/2000/svg", "text");
        el.setAttribute("text-anchor", "middle");
        el.setAttribute("dominant-baseline", "central");
        el.setAttribute("font-size", String(size(n)));
        el.setAttribute("class", `cw ${i < 5 ? "cw0" : i < 12 ? "cw1" : "cw2"}`);
        el.textContent = w;
        svg.appendChild(el);
        const bb = el.getBBox(), bw = bb.width, bh = bb.height * 0.78;
        for (let k = 0; k < 3000; k++) {
          const an = k * 0.1, r = 2.2 * an;
          const x = W / 2 + r * Math.cos(an) * 1.9, y = H / 2 + r * Math.sin(an);
          const rc = { x: x - bw / 2, y: y - bh / 2, w: bw, h: bh };
          if (rc.x < 8 || rc.y < 6 || rc.x + bw > W - 8 || rc.y + bh > H - 6 || hit(rc)) continue;
          placed.push(rc);
          el.setAttribute("x", String(x));
          el.setAttribute("y", String(y));
          return;
        }
        el.remove();
      });
    };
    draw();
    let timer = 0;
    const onResize = () => { window.clearTimeout(timer); timer = window.setTimeout(draw, 200); };
    window.addEventListener("resize", onResize);
    return () => { window.removeEventListener("resize", onResize); window.clearTimeout(timer); };
  }, [b.words]);

  return <svg ref={ref} className="cloud" viewBox="0 0 1000 400" role="img" aria-label={t("wordcloudAria")} />;
}
