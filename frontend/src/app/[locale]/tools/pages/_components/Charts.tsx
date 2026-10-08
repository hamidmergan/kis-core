"use client";

import { useLayoutEffect, useRef } from "react";
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

/** A tidy top for the value axis: 1, 2 or 5 times a power of ten. */
function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const step = [1, 2, 2.5, 5, 10].find((m) => m * p >= v) ?? 10;
  return step * p;
}

export function Chart({ b }: { b: ChartBlock }) {
  const num = useNumber();
  const W = 1000, H = 380, L = 64, R = 20, T0 = 30, B = 56;
  const n = b.categories.length;
  const max = niceMax(Math.max(...b.series.flatMap((s) => s.values)));
  const sx = (i: number) => L + (n === 1 ? 0.5 : i / (n - 1)) * (W - L - R);
  const sy = (v: number) => H - B - (v / max) * (H - T0 - B);
  const bw = (W - L - R) / n;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={b.caption}>
      {[0, 1, 2, 3, 4].map((k) => {
        const v = (max * k) / 4, y = sy(v);
        return (
          <g key={k}>
            <line className="grid-line" x1={L} x2={W - R} y1={y} y2={y} strokeWidth={2} />
            <text className="axis" x={L - 10} y={y + 5} textAnchor="end" fontSize={14}>{num(v)}</text>
          </g>
        );
      })}
      {b.chart_type === "bar"
        ? b.series[0].values.map((v, i) => {
            const h = (v / max) * (H - T0 - B);
            return <rect key={i} className="bar" x={L + i * bw + bw * 0.2} y={H - B - h} width={bw * 0.6} height={h} rx={6} />;
          })
        : b.series.map((s, k) => (
            <g key={k}>
              <polyline className={`s${k}`} fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round"
                strokeDasharray={k ? "10 8" : undefined} points={s.values.map((v, i) => `${sx(i)},${sy(v)}`).join(" ")} />
              {!k && s.values.map((v, i) => <circle key={i} className="dot" cx={sx(i)} cy={sy(v)} r={7} strokeWidth={3} />)}
            </g>
          ))}
      {b.categories.map((c, i) => (
        <text key={i} className="axis" x={b.chart_type === "bar" ? L + i * bw + bw / 2 : sx(i)} y={H - B + 24} textAnchor="middle" fontSize={14}>{c}</text>
      ))}
      {b.x_label && <text className="axis-title" x={W - R} y={H - 8} textAnchor="end" fontSize={14}>{b.x_label}</text>}
      {b.y_label && <text className="axis-title" x={L} y={T0 - 10} fontSize={14}>{b.y_label}</text>}
    </svg>
  );
}

const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);

/** The page's sections around its title, right side top to bottom, then the left side back up. */
export function MindMap({ b }: { b: MindBlock }) {
  const t = useTranslations("tools.pages");
  const W = 1280, CX = 640, NODE_DX = 250, LEAF_GAP = 30;
  const n = b.branches.length;
  const right = b.branches.slice(0, Math.ceil(n / 2));
  const left = b.branches.slice(Math.ceil(n / 2)).reverse();
  const slot = (br: MindBlock["branches"][number]) => Math.max(70, br.leaves.length * LEAF_GAP + 20);
  const H = Math.max(260, Math.max(right.reduce((a, br) => a + slot(br), 0), left.reduce((a, br) => a + slot(br), 0)) + 60);
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
      const title = cut(br.title, 26);
      const hw = Math.min(124, Math.max(56, title.length * 4.6 + 24));
      const nodeX = CX + dir * NODE_DX;
      const mx = (CX + nodeX) / 2;
      const ex = nodeX + dir * hw, dx = nodeX + dir * (hw + 40);
      return (
        <g key={`${dir}${k}`} className="mm-br" tabIndex={0} role="link" aria-label={t("jumpTo", { title: br.title })}
          onClick={() => go(br.to)} onKeyDown={(e) => { if (e.key === "Enter") go(br.to); }}>
          <path className="mm-edge" d={`M${CX},${CY} C${mx},${CY} ${mx},${ny} ${nodeX},${ny}`} strokeWidth={5} strokeLinecap="round" />
          {br.leaves.map((l, i) => {
            const ly = ny + (i - (br.leaves.length - 1) / 2) * LEAF_GAP;
            return (
              <g key={i}>
                <path className="mm-edge" d={`M${ex},${ny} C${(ex + dx) / 2},${ny} ${(ex + dx) / 2},${ly} ${dx},${ly}`} strokeWidth={2.5} />
                <circle className="mm-leaf-dot" cx={dx} cy={ly} r={4.5} />
                <text className="mm-leaf" x={dx + dir * 12} y={ly + 5} textAnchor={dir < 0 ? "end" : "start"} fontSize={15}>{cut(l, 26)}</text>
              </g>
            );
          })}
          <rect className="mm-node" x={nodeX - hw} y={ny - 22} width={hw * 2} height={44} rx={22} strokeWidth={3} />
          <text className="mm-node-text" x={nodeX} y={ny + 6} textAnchor="middle" fontSize={16}>{title}</text>
        </g>
      );
    });
  };

  const center = cut(b.center, 22);
  const cw = Math.min(240, center.length * 11 + 44);
  return (
    <svg className="mm-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("mindmapAria")}>
      {side(right, 1)}
      {side(left, -1)}
      <rect className="mm-center" x={CX - cw / 2} y={CY - 28} width={cw} height={56} rx={28} />
      <text className="mm-center-text" x={CX} y={CY + 7} textAnchor="middle" fontSize={20}>{center}</text>
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
