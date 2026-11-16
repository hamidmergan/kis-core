"use client";

import { useLayoutEffect, useRef } from "react";
import { useLocale, useTranslations } from "next-intl";
import { sizedWords } from "../_lib/cloud";
import type { Block } from "../_lib/types";

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
      const placed: { x: number; y: number; w: number; h: number }[] = [];
      const hit = (r: { x: number; y: number; w: number; h: number }) =>
        placed.some((p) => r.x < p.x + p.w + 8 && r.x + r.w + 8 > p.x && r.y < p.y + p.h + 3 && r.y + r.h + 3 > p.y);
      sizedWords(b.words).forEach(({ word, size }, i) => {
        const el = document.createElementNS("http://www.w3.org/2000/svg", "text");
        el.setAttribute("text-anchor", "middle");
        el.setAttribute("dominant-baseline", "central");
        el.setAttribute("font-size", String(size));
        el.setAttribute("class", `cw ${i < 5 ? "cw0" : i < 12 ? "cw1" : "cw2"}`);
        el.textContent = word;
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
