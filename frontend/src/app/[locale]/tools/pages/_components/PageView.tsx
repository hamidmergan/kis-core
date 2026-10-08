"use client";

import { useContext } from "react";
import { useTranslations } from "next-intl";
import {
  ArrowCounterClockwise,
  ArrowDown,
  ArrowUUpLeft,
  ArrowUUpRight,
  ArrowUp,
  Check,
  Eye,
  EyeSlash,
  Info,
  Lightbulb,
  Trash,
  Warning,
  X,
} from "@phosphor-icons/react";
import type { Block, CardIcon, Limits, Page, Section } from "../_lib/types";
import { Chart, MindMap, WordCloud, useNumber } from "./Charts";
import { EditCtx, Txt } from "./Txt";
import "./page.css";

const ICONS: Record<CardIcon, typeof Info> = { info: Info, check: Check, x: X, warning: Warning, idea: Lightbulb };

/** What the editor hands the page, absent for every reader. */
export interface EditControls {
  canUndo: boolean;
  canRedo: boolean;
  dirty: boolean;
  saving: boolean;
  error: string | null;
  onUndo: () => void;
  onRedo: () => void;
  onReset: () => void;
  onSave: () => void;
  onSection: (index: number, action: "up" | "down" | "hide" | "del") => void;
}

interface Props {
  page: Page;
  limits: Limits;
  imageBase: string;
  edit?: EditControls | null;
}

/** Figure and table numbers in reading order, counted over what is actually shown. */
function numbering(page: Page, editing: boolean): Map<string, number> {
  const nums = new Map<string, number>();
  let fig = 0, tab = 0;
  page.sections.forEach((s, i) => {
    if (s.hero || (s.hidden && !editing)) return;
    s.blocks.forEach((b, j) => {
      const key = `${i}.${j}`;
      if (b.kind === "table") nums.set(key, ++tab);
      else if (b.kind === "image" ? b.caption || editing : ["chart", "mindmap", "wordcloud"].includes(b.kind)) nums.set(key, ++fig);
    });
  });
  return nums;
}

export default function PageView({ page, limits, imageBase, edit }: Props) {
  const t = useTranslations("tools.pages");
  const { editing } = useContext(EditCtx);
  const nums = numbering(page, editing);
  const n = page.sections.length;

  return (
    <div className={`kis-page${editing ? " editing" : ""}`}>
      <main className="wrap">
        {edit && (
          <div className="ed-only ed-actions">
            <button type="button" className="ed-btn icon-only" disabled={!edit.canUndo} onClick={edit.onUndo} aria-label={t("undo")} title={t("undoTitle")}>
              <ArrowUUpLeft size={14} weight="bold" />
            </button>
            <button type="button" className="ed-btn icon-only" disabled={!edit.canRedo} onClick={edit.onRedo} aria-label={t("redo")} title={t("redoTitle")}>
              <ArrowUUpRight size={14} weight="bold" />
            </button>
            <button type="button" className="ed-btn reset" disabled={!edit.dirty || edit.saving} onClick={edit.onReset} title={t("resetTitle")}>
              <ArrowCounterClockwise size={12} weight="bold" />
              {t("reset")}
            </button>
            <button type="button" className="ed-btn save" disabled={!edit.dirty || edit.saving} onClick={edit.onSave}>
              {t("save")}
            </button>
          </div>
        )}
        {page.sections.map((s, i) => (
          <SectionView key={s.id} s={s} i={i} n={n} limits={limits} imageBase={imageBase} nums={nums} edit={edit} />
        ))}
        {edit && (
          <div className="ed-only ed-save" style={{ flexDirection: "column", alignItems: "flex-end" }}>
            <button type="button" className="ed-btn save" disabled={!edit.dirty || edit.saving} onClick={edit.onSave}>
              {t("save")}
            </button>
            {edit.error && <p className="ed-error" role="alert">{edit.error}</p>}
          </div>
        )}
        <footer className="pfoot">
          <Txt path="footer" value={page.footer} as="p" max={limits.long} />
        </footer>
      </main>
    </div>
  );
}

function Tools({ s, i, n, edit }: { s: Section; i: number; n: number; edit: EditControls }) {
  const t = useTranslations("tools.pages");
  return (
    <div className="ed-only ed-tools">
      <button type="button" className="ed-btn" disabled={i === 0} onClick={() => edit.onSection(i, "up")}>
        <ArrowUp size={12} weight="bold" />{t("up")}
      </button>
      <button type="button" className="ed-btn" disabled={i === n - 1} onClick={() => edit.onSection(i, "down")}>
        <ArrowDown size={12} weight="bold" />{t("down")}
      </button>
      <button type="button" className="ed-btn" onClick={() => edit.onSection(i, "hide")}>
        {s.hidden ? <Eye size={12} weight="bold" /> : <EyeSlash size={12} weight="bold" />}
        {s.hidden ? t("show") : t("hide")}
      </button>
      <button type="button" className="ed-btn del" onClick={() => edit.onSection(i, "del")}>
        <Trash size={12} weight="bold" />{t("remove")}
      </button>
    </div>
  );
}

interface SectionProps {
  s: Section;
  i: number;
  n: number;
  limits: Limits;
  imageBase: string;
  nums: Map<string, number>;
  edit?: EditControls | null;
}

function SectionView({ s, i, n, limits, imageBase, nums, edit }: SectionProps) {
  const p = `sections.${i}`;
  const cls = s.hidden ? " is-hidden" : "";
  if (s.hero) {
    const j = s.blocks.findIndex((b) => b.kind === "image");
    const img = j >= 0 ? (s.blocks[j] as Extract<Block, { kind: "image" }>) : null;
    return (
      <section id={s.id} className={`hero${img ? "" : " solo"}${cls}`} data-i={i}>
        {edit && <Tools s={s} i={i} n={n} edit={edit} />}
        <div>
          <Txt path={`${p}.title`} value={s.title} as="h1" max={limits.short} />
          <Txt path={`${p}.lead`} value={s.lead} as="p" className="lead" max={limits.long} />
          <Txt path={`${p}.meta`} value={s.meta} as="p" className="meta" max={limits.long} />
        </div>
        {img && (
          <figure className="img" data-d={`${p}.blocks.${j}`}>
            {/* eslint-disable-next-line @next/next/no-img-element -- served by our own route behind the session */}
            <img src={`${imageBase}/${img.src}`} alt={img.alt} />
          </figure>
        )}
      </section>
    );
  }
  const blocks = s.blocks.map((b, j) => (
    <div className="blk" data-d={`${p}.blocks.${j}`} key={j}>
      <BlockView b={b} p={`${p}.blocks.${j}`} limits={limits} imageBase={imageBase} num={nums.get(`${i}.${j}`)} />
    </div>
  ));
  // An image beside one other block sits side by side, everything else stacks.
  const duo = s.blocks.length === 2 && s.blocks.some((b) => b.kind === "image");
  return (
    <section id={s.id} className={cls.trim()} data-i={i}>
      {edit && <Tools s={s} i={i} n={n} edit={edit} />}
      <div className="txt">
        <Txt path={`${p}.title`} value={s.title} as="h2" max={limits.short} />
        <Txt path={`${p}.lead`} value={s.lead} as="p" className="lead" max={limits.long} />
      </div>
      {duo ? <div className="duo">{blocks}</div> : blocks}
    </section>
  );
}

function Caption({ p, b, num, kind, limits }: { p: string; b: { caption: string }; num?: number; kind: "figure" | "table"; limits: Limits }) {
  const t = useTranslations("tools.pages");
  const { editing } = useContext(EditCtx);
  if (num == null || (!b.caption && !editing)) return null;
  return (
    <figcaption>
      <b>{t(kind, { n: num })}</b>
      <Txt path={`${p}.caption`} value={b.caption} max={limits.short} />
    </figcaption>
  );
}

function BlockView({ b, p, limits, imageBase, num }: { b: Block; p: string; limits: Limits; imageBase: string; num?: number }) {
  const fmt = useNumber();
  const S = limits.short, I = limits.item;
  switch (b.kind) {
    case "bullets":
      return b.items.length <= 4 ? (
        <div className="gist">
          {b.items.map((v, i) => (
            <div key={i} data-d={`${p}.items.${i}`}><Txt path={`${p}.items.${i}`} value={v} max={I} /></div>
          ))}
        </div>
      ) : (
        <ul className="bul">
          {b.items.map((v, i) => (
            <li key={i} data-d={`${p}.items.${i}`}><Txt path={`${p}.items.${i}`} value={v} max={I} /></li>
          ))}
        </ul>
      );
    case "highlight":
      return (
        <div className="hl">
          <Txt path={`${p}.key`} value={b.key} as="div" className="k" max={S} />
          <Txt path={`${p}.text`} value={b.text} as="div" className="x" max={I} />
        </div>
      );
    case "cards": {
      const cols = b.cols ?? Math.min(b.cards.length, b.cards.length === 4 ? 2 : 3);
      return (
        <div className="panel">
          <div className={`grid g${cols}`}>
            {b.cards.map((c, i) => {
              const Icon = ICONS[c.icon] ?? Info;
              return (
                <div className="cell" key={i} data-d={`${p}.cards.${i}`}>
                  <div className={`ic ${c.icon}`}><Icon size={18} weight="bold" aria-hidden="true" /></div>
                  <Txt path={`${p}.cards.${i}.title`} value={c.title} as="h3" max={S} />
                  <Txt path={`${p}.cards.${i}.text`} value={c.text} as="p" max={I} />
                </div>
              );
            })}
          </div>
        </div>
      );
    }
    case "steps":
      return (
        <div className="panel">
          <div className={`grid g${Math.min(4, b.steps.length)}`}>
            {b.steps.map((s, i) => (
              <div className="cell" key={i} data-d={`${p}.steps.${i}`}>
                <span className="num">{i + 1}</span>
                <Txt path={`${p}.steps.${i}.title`} value={s.title} as="h3" max={S} />
                <Txt path={`${p}.steps.${i}.text`} value={s.text} as="p" max={I} />
              </div>
            ))}
          </div>
        </div>
      );
    case "figures":
      return (
        <div className="panel">
          <div className={`grid g${Math.min(4, b.figures.length)}`}>
            {b.figures.map((f, i) => (
              <div className="cell fig-n" key={i} data-d={`${p}.figures.${i}`}>
                <Txt path={`${p}.figures.${i}.value`} value={f.value} as="div" className="v" max={24} />
                <Txt path={`${p}.figures.${i}.label`} value={f.label} as="div" className="l" max={S} />
              </div>
            ))}
          </div>
        </div>
      );
    case "bars": {
      const max = b.max || Math.max(...b.bars.map((x) => x.value)) || 1;
      return (
        <div className="panel">
          {b.bars.map((x, i) => (
            <div className="barrow" key={i} data-d={`${p}.bars.${i}`}>
              <div>
                <Txt path={`${p}.bars.${i}.label`} value={x.label} as="div" className="bl" max={S} />
                <Txt path={`${p}.bars.${i}.text`} value={x.text} as="div" className="bt" max={I} />
              </div>
              <div className="track">
                <i style={{ width: `${Math.max((x.value / max) * 80, 1)}%` }} />
                <b>{fmt(x.value)}</b>
              </div>
            </div>
          ))}
        </div>
      );
    }
    case "table":
      return (
        <figure>
          <div className="panel">
            <div className="tbl">
              <table className="stack">
                <thead>
                  <tr>{b.header.map((h, i) => <th key={i}><Txt path={`${p}.header.${i}`} value={h} max={S} keep /></th>)}</tr>
                </thead>
                <tbody>
                  {b.rows.map((r, i) => (
                    <tr key={i} data-d={`${p}.rows.${i}`}>
                      {r.map((c, j) => (
                        <td key={j} data-label={j ? b.header[j] : undefined}>
                          <Txt path={`${p}.rows.${i}.${j}`} value={c} max={S} keep />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <Caption p={p} b={b} num={num} kind="table" limits={limits} />
        </figure>
      );
    case "image":
      return (
        <figure className="img">
          {/* eslint-disable-next-line @next/next/no-img-element -- served by our own route behind the session */}
          <img src={`${imageBase}/${b.src}`} alt={b.alt} />
          <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
        </figure>
      );
    case "chart":
      return (
        <figure>
          <div className="panel">
            <Chart b={b} />
            {b.series.length > 1 && (
              <div className="legend">
                {b.series.map((s, i) => <span key={i}><i className={`s${i}`} />{s.name}</span>)}
              </div>
            )}
          </div>
          <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
        </figure>
      );
    case "mindmap":
      return (
        <figure>
          <div className="panel">
            <MindMap b={b} />
            <ul className="mm-list">
              {b.branches.map((br, i) => (
                <li key={i}><b>{br.title}</b><span>{br.leaves.join(", ")}</span></li>
              ))}
            </ul>
          </div>
          <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
        </figure>
      );
    case "wordcloud":
      return (
        <figure>
          <div className="panel"><WordCloud b={b} /></div>
          <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
        </figure>
      );
  }
}
