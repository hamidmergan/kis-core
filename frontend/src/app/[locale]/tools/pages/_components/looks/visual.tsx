"use client";

import { useContext, type CSSProperties, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import type { Block } from "../../_lib/types";
import type { LookProps, Looks } from "./registry";
import { Caption, DataButton, Picture } from "./shared";
import { useNumber } from "../Charts";
import { EditCtx, Txt } from "../Txt";
import "./visual.css";

type MindBlock = Extract<Block, { kind: "mindmap" }>;
type Branch = MindBlock["branches"][number];
type CloudBlock = Extract<Block, { kind: "wordcloud" }>;

const n1 = (v: number) => Number(v.toFixed(1));

/* ---------- image ---------- */

function ImgBanner({ b, p, limits, imageBase, num }: LookProps<"image">) {
  return (
    <figure className="img v-vi v-im-banner">
      <Picture src={b.src} alt={b.alt} p={p} imageBase={imageBase} />
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

/** The picture on the right, its caption hangs under the empty left column and points at it. */
function ImgOffset({ b, p, limits, imageBase, num }: LookProps<"image">) {
  return (
    <figure className="img v-vi v-im-offset">
      <div className="v-im-offset-in">
        <Picture src={b.src} alt={b.alt} p={p} imageBase={imageBase} />
        <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
      </div>
    </figure>
  );
}

/** A 4:3 picture on the left, the caption stands beside it under a rule. */
function ImgSide({ b, p, limits, imageBase, num }: LookProps<"image">) {
  return (
    <figure className="img v-vi v-im-side">
      <div className="v-im-side-in">
        <Picture src={b.src} alt={b.alt} p={p} imageBase={imageBase} />
        <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
      </div>
    </figure>
  );
}

/* ---------- mindmap ---------- */

const go = (to: string) => {
  const el = to ? document.getElementById(to) : null;
  if (el) el.scrollIntoView({ behavior: "smooth" });
};

/** A branch title in HTML, a link to its section for readers, plain text while editing. */
function BranchTitle({ br, path, max, className, children }: { br: Branch; path: string; max: number; className: string; children?: ReactNode }) {
  const t = useTranslations("tools.pages");
  const { editing } = useContext(EditCtx);
  const link = !!br.to && !editing;
  return (
    <div className={className} role={link ? "link" : undefined} tabIndex={link ? 0 : undefined}
      aria-label={link ? t("jumpTo", { title: br.title }) : undefined}
      onClick={link ? () => go(br.to) : undefined}
      onKeyDown={link ? (e) => { if (e.key === "Enter") go(br.to); } : undefined}>
      <Txt path={`${path}.title`} value={br.title} as="b" max={max} />
      {children}
    </div>
  );
}

function Leaves({ br, path, max, className }: { br: Branch; path: string; max: number; className: string }) {
  if (!br.leaves.length) return null;
  return (
    <ul className={className}>
      {br.leaves.map((l, k) => (
        <li key={k} data-d={`${path}.leaves.${k}`}><Txt path={`${path}.leaves.${k}`} value={l} max={max} /></li>
      ))}
    </ul>
  );
}

/** The branches around the centre as an SVG, on a narrow field a list with the centre on top. */
function MmRadial({ b, p, limits, num }: LookProps<"mindmap">) {
  const t = useTranslations("tools.pages");
  const W = 1040, H = 560, cx = 520, cy = 280;
  const R1 = { x: 250, y: 140 }, R2 = { x: 370, y: 232 };
  const n = b.branches.length;
  const parts = b.branches.map((br, i) => {
    const a = (i / n) * Math.PI * 2;
    const bx = n1(cx + R1.x * Math.cos(a)), by = n1(cy + R1.y * Math.sin(a));
    const m = br.leaves.length;
    const w = Math.round(br.title.length * 11 + 28);
    const link = !!br.to;
    return (
      <g key={i} className={link ? "v-mm-link" : undefined} tabIndex={link ? 0 : undefined} role={link ? "link" : undefined}
        aria-label={link ? t("jumpTo", { title: br.title }) : undefined}
        onClick={link ? () => go(br.to) : undefined} onKeyDown={link ? (e) => { if (e.key === "Enter") go(br.to); } : undefined}>
        <line x1={cx} y1={cy} x2={bx} y2={by} className="v-mm-l1" />
        {br.leaves.map((leaf, j) => {
          const la = a + (j - (m - 1) / 2) * 0.24;
          const lx = n1(cx + R2.x * Math.cos(la)), ly = n1(cy + R2.y * Math.sin(la));
          const c = Math.cos(la);
          const anchor = c > 0.2 ? "start" : c < -0.2 ? "end" : "middle";
          const dx = c > 0.2 ? 10 : c < -0.2 ? -10 : 0;
          const dy = Math.abs(c) <= 0.2 ? (Math.sin(la) > 0 ? 24 : -12) : 6;
          return (
            <g key={j}>
              <line x1={bx} y1={by} x2={lx} y2={ly} className="v-mm-l2" />
              <circle cx={lx} cy={ly} r={4} className="v-mm-dot" />
              <text x={lx + dx} y={ly + dy} textAnchor={anchor} className="v-mm-leaf">{leaf}</text>
            </g>
          );
        })}
        <rect x={n1(bx - w / 2)} y={by - 19} width={w} height={38} rx={8} className="v-mm-box" />
        <text x={bx} y={by + 7} textAnchor="middle" className="v-mm-branch">{br.title}</text>
      </g>
    );
  });
  return (
    <figure className="v-vi v-mm-radial has-over">
      <DataButton p={p} />
      <svg viewBox={`0 0 ${W} ${H}`} className="v-mm-radial-svg" role="img" aria-label={t("mindmapAria")}>
        {parts}
        <ellipse cx={cx} cy={cy} rx={118} ry={38} className="v-mm-center" />
        <text x={cx} y={cy + 7} textAnchor="middle" className="v-mm-t-center">{b.center}</text>
      </svg>
      <div className="v-mm-radial-list">
        <div className="v-mm-radial-root"><Txt path={`${p}.center`} value={b.center} max={limits.mapLabel} /></div>
        <div className="v-mm-radial-grid">
          {b.branches.map((br, i) => (
            <div className="v-mm-radial-b" key={i} data-d={`${p}.branches.${i}`}>
              <BranchTitle br={br} path={`${p}.branches.${i}`} max={limits.mapLabel} className="v-mm-radial-t" />
              <Leaves br={br} path={`${p}.branches.${i}`} max={limits.mapLabel} className="v-mm-radial-leaves" />
            </div>
          ))}
        </div>
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

/** The root on the left, a rail with the branches, each with a rail of its leaves, all in HTML. */
function MmTree({ b, p, limits, num }: LookProps<"mindmap">) {
  return (
    <figure className="v-vi v-mm-tree has-over">
      <DataButton p={p} />
      <div className="v-mm-tree-in">
        <div className="v-mm-tree-root"><Txt path={`${p}.center`} value={b.center} max={limits.mapLabel} /></div>
        <ol className="v-mm-tree-l1">
          {b.branches.map((br, i) => (
            <li key={i} data-d={`${p}.branches.${i}`}>
              <BranchTitle br={br} path={`${p}.branches.${i}`} max={limits.mapLabel} className="v-mm-tree-t" />
              <Leaves br={br} path={`${p}.branches.${i}`} max={limits.mapLabel} className="v-mm-tree-l2" />
            </li>
          ))}
        </ol>
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

/** The root on top, a rail under it, every branch a column with its leaves as rows. */
function MmCols({ b, p, limits, num }: LookProps<"mindmap">) {
  const n = b.branches.length;
  return (
    <figure className="v-vi v-mm-cols has-over">
      <DataButton p={p} />
      <div className={`v-mm-cols-in${n >= 5 ? " v-mm-cols-many" : ""}`}>
        <div className="v-mm-cols-root"><span><Txt path={`${p}.center`} value={b.center} max={limits.mapLabel} /></span></div>
        <div className="v-mm-cols-row" style={{ "--v-mm-n": n } as CSSProperties}>
          {b.branches.map((br, i) => (
            <div className="v-mm-cols-b" key={i} data-d={`${p}.branches.${i}`}>
              <BranchTitle br={br} path={`${p}.branches.${i}`} max={limits.mapLabel} className="v-mm-cols-t" />
              <Leaves br={br} path={`${p}.branches.${i}`} max={limits.mapLabel} className="v-mm-cols-leaves" />
            </div>
          ))}
        </div>
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

/* ---------- wordcloud ---------- */

/** The words by count, each with its place in the block so the bin removes the right pair. */
const ranked = (b: CloudBlock) =>
  b.words.map(([w, n], i) => ({ w, n, i })).sort((a, c) => c.n - a.n);

/** 0 for the rarest word, 1 for the most frequent. */
const weight = (n: number, max: number, min: number) => (n - min) / (max - min || 1);

/** The words wrapped like a cloud, the size follows the count, big and small ones mixed. */
function WcCloud({ b, p, limits, num }: LookProps<"wordcloud">) {
  const s = ranked(b);
  const max = s[0]?.n ?? 1, min = s[s.length - 1]?.n ?? 0;
  const third = Math.ceil(s.length / 3);
  const big = s.slice(0, third), mid = s.slice(third, 2 * third), small = s.slice(2 * third);
  const order: typeof s = [];
  for (let i = 0; i < third; i++) {
    if (small[i]) order.push(small[i]);
    if (big[i]) order.push(big[i]);
    if (mid[i]) order.push(mid[i]);
  }
  return (
    <figure className="v-vi v-wc-cloud has-over">
      <DataButton p={p} />
      <div className="v-wc-cloud-box">
        {order.map(({ w, n, i }) => {
          const t = weight(n, max, min);
          const cls = t > 0.5 ? "v-wc-cloud-a" : t > 0.2 ? "v-wc-cloud-b" : "v-wc-cloud-c";
          return <span key={i} className={cls} style={{ fontSize: `${Math.round(15 + t * 31)}px` }} data-d={`${p}.words.${i}`}>{w}</span>;
        })}
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

/** Every word a label in one of three sizes, its count beside it. */
function WcTags({ b, p, limits, num }: LookProps<"wordcloud">) {
  const fmt = useNumber();
  const s = ranked(b);
  const max = s[0]?.n ?? 1, min = s[s.length - 1]?.n ?? 0;
  return (
    <figure className="v-vi v-wc-tags has-over">
      <DataButton p={p} />
      <div className="v-wc-tags-box">
        {s.map(({ w, n, i }) => {
          const t = weight(n, max, min);
          const cls = t >= 0.6 ? "v-wc-tag-a" : t >= 0.25 ? "v-wc-tag-b" : "v-wc-tag-c";
          return <span key={i} className={`v-wc-tag ${cls}`} data-d={`${p}.words.${i}`}>{w}<i>{fmt(n)}</i></span>;
        })}
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

/** The words ranked in two columns, the count as a fine line and a number. */
function WcRank({ b, p, limits, num }: LookProps<"wordcloud">) {
  const fmt = useNumber();
  const s = ranked(b);
  const max = s[0]?.n ?? 1;
  const half = Math.ceil(s.length / 2);
  const row = ({ w, n, i }: (typeof s)[number], rank: number) => (
    <li key={i} data-d={`${p}.words.${i}`}>
      <span className="v-wc-rank-no">{fmt(rank)}</span>
      <span className="v-wc-rank-w">{w}</span>
      <span className="v-wc-rank-bar" style={{ width: `${Math.round((n / max) * 100)}%` }} />
      <span className="v-wc-rank-n">{fmt(n)}</span>
    </li>
  );
  return (
    <figure className="v-vi v-wc-rank has-over">
      <DataButton p={p} />
      <div className="v-wc-rank-in">
        <ol className="v-wc-rank-col">{s.slice(0, half).map((x, k) => row(x, k + 1))}</ol>
        <ol className="v-wc-rank-col" start={half + 1}>{s.slice(half).map((x, k) => row(x, k + half + 1))}</ol>
      </div>
      <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
    </figure>
  );
}

export const LOOKS_VISUAL: Looks = {
  image: [
    { name: "Breites Banner", View: ImgBanner },
    { name: "Versetzte Unterschrift", fits: (b) => !!b.caption, View: ImgOffset },
    { name: "Unterschrift seitlich", fits: (b) => !!b.caption, View: ImgSide },
  ],
  mindmap: [
    // Labels sit inside the SVG, so this one takes only short ones and a few leaves per branch.
    {
      name: "Radial",
      fits: (b) => b.branches.length >= 3 && b.branches.length <= 6 && b.center.length <= 18
        && b.branches.every((br) => br.title.length <= 14 && br.leaves.length <= 3 && br.leaves.every((l) => l.length <= 18)),
      View: MmRadial,
    },
    { name: "Baum nach rechts", View: MmTree },
    { name: "Äste als Spalten", fits: (b) => b.branches.length <= 6, View: MmCols },
  ],
  wordcloud: [
    { name: "Wolke", View: WcCloud },
    { name: "Etiketten", View: WcTags },
    { name: "Rangliste", View: WcRank },
  ],
};
