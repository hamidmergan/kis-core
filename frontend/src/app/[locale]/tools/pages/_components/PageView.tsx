"use client";

import { Fragment, createContext, useContext } from "react";
import { useTranslations } from "next-intl";
import ToolBackLink from "@/components/ui/ToolBackLink";
import {
  ArrowCounterClockwise,
  ArrowDown,
  ArrowUUpLeft,
  ArrowUUpRight,
  ArrowUp,
  ChartBar,
  Check,
  Eye,
  EyeSlash,
  Image as ImageIcon,
  Info,
  Lightbulb,
  ListBullets,
  Plus,
  Table,
  TextT,
  Trash,
  Warning,
  X,
} from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import { HEADINGS, type Block, type CardIcon, type Design, type Heading, type Limits, type Page, type Section } from "../_lib/types";
import { Chart, MindMap, WordCloud, useNumber } from "./Charts";
import { EditCtx, Txt } from "./Txt";
import "./page.css";

// Only signs that tell cards apart, "none" and the old "info" draw nothing.
const ICONS: Partial<Record<CardIcon, typeof Info>> = { check: Check, x: X, warning: Warning, idea: Lightbulb };

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
  /** Where an added section shows its title. */
  onHeading: (index: number, heading: Heading) => void;
  /** Pictures being drawn: the new name and the one it replaces, "" for a new picture. */
  pending: ReadonlyMap<string, string>;
  imagesFull: boolean;
  onAddSection: (after: number) => void;
  onPick: (section: number, field: number, kind: FieldKind) => void;
  onGrow: (path: string, what: "item" | "row" | "col") => void;
  onImage: (path: string) => void;
  /** A title block without a picture gets one. */
  onHeroImage: (section: number) => void;
  onData: (path: string) => void;
}

/** What an empty field of an added section can become. */
export type FieldKind = "text" | "image" | "table" | "chart" | "list" | "note";
const FIELDS: { kind: FieldKind; icon: typeof Info }[] = [
  { kind: "text", icon: TextT }, { kind: "image", icon: ImageIcon }, { kind: "table", icon: Table },
  { kind: "chart", icon: ChartBar }, { kind: "list", icon: ListBullets }, { kind: "note", icon: Info },
];

/** The editor's controls for the blocks deep inside the page, null for every reader. */
const PageEdit = createContext<EditControls | null>(null);

// Figure and table labels belong to the page, so they follow its language, not the reader's.
const CAPTION_WORDS: Record<string, { figure: string; table: string }> = {
  de: { figure: "Abbildung", table: "Tabelle" }, en: { figure: "Figure", table: "Table" },
  fr: { figure: "Figure", table: "Tableau" }, es: { figure: "Figura", table: "Tabla" },
  it: { figure: "Figura", table: "Tabella" }, tr: { figure: "Şekil", table: "Tablo" },
  uk: { figure: "Рисунок", table: "Таблиця" }, pl: { figure: "Rysunek", table: "Tabela" },
  zh: { figure: "图", table: "表" },
};
const PageLang = createContext("de");

interface Props {
  page: Page;
  limits: Limits;
  imageBase: string;
  edit?: EditControls | null;
  back?: { href: string; label: string };
  /** Buttons on the right of the back link's row. */
  tools?: React.ReactNode;
}

/** Figure and table numbers in reading order, counted over what is actually shown. */
function numbering(page: Page, editing: boolean): Map<string, number> {
  const nums = new Map<string, number>();
  let fig = 0, tab = 0;
  page.sections.forEach((s, i) => {
    // The title picture is no figure of the text, it gets no number.
    if (s.hero || s.id === "cover" || (s.hidden && !editing)) return;
    s.blocks.forEach((b, j) => {
      const key = `${i}.${j}`;
      if (b.kind === "table") nums.set(key, ++tab);
      else if (b.kind === "image" ? b.caption || editing : ["chart", "mindmap", "wordcloud"].includes(b.kind)) nums.set(key, ++fig);
    });
  });
  return nums;
}

export default function PageView({ page, limits, imageBase, edit, back, tools }: Props) {
  const t = useTranslations("tools.pages");
  const { editing } = useContext(EditCtx);
  const nums = numbering(page, editing);
  const n = page.sections.length;
  const design: Design = page.design ?? "chapters";
  const hasCover = page.sections.some((x) => x.id === "cover" && x.blocks.some((b) => b.kind === "image"));
  // Chapters count only the sections of the subject, not the title, summary, map or words.
  const chapters = new Map<number, number>();
  page.sections.forEach((s, i) => {
    if (isContent(s) && s.heading !== "none" && !(s.hidden && !editing)) chapters.set(i, chapters.size + 1);
  });

  return (
    <PageEdit.Provider value={edit ?? null}>
    <PageLang.Provider value={page.lang}>
    <div className={`kis-page d-${design}${editing ? " editing" : ""}`} lang={page.lang}>
      <main className="wrap">
        <div className="top-row">
          {back && <ToolBackLink href={back.href} label={back.label} />}
          {tools && <div className="top-tools">{tools}</div>}
        </div>
        {edit && (
          <div className="ed-only ed-actions ed-row">
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
          <Fragment key={s.id}>
            <SectionView s={s} i={i} n={n} limits={limits} imageBase={imageBase} nums={nums} edit={edit}
              design={design} chapter={chapters.get(i)} hasCover={hasCover} />
            {edit && <AddSection after={i} full={n >= limits.sections} max={limits.sections} onAdd={edit.onAddSection} />}
          </Fragment>
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
    </PageLang.Provider>
    </PageEdit.Provider>
  );
}

/** The round plus between two sections, it opens the choice of a layout for a new one. */
function AddSection({ after, full, max, onAdd }: { after: number; full: boolean; max: number; onAdd: (after: number) => void }) {
  const t = useTranslations("tools.pages");
  return (
    <div className="ed-only ed-add">
      <button type="button" disabled={full} onClick={() => onAdd(after)} aria-label={t("addSection")}
        title={full ? t("addSectionFull", { max }) : t("addSection")}>
        <Plus size={15} weight="bold" />
      </button>
    </div>
  );
}

/** An empty field of an added section: while editing the choice of its content, for readers nothing. */
function EmptyField({ i, j, limits }: { i: number; j: number; limits: Limits }) {
  const t = useTranslations("tools.pages");
  const ed = useContext(PageEdit);
  const { editing } = useContext(EditCtx);
  if (!ed || !editing) return <div className="fld fld-empty" />;
  return (
    <div className="fld fld-empty">
      <div className="fld-pick">
        <span>{t("fieldAsk")}</span>
        <div className="fld-opts">
          {FIELDS.map(({ kind, icon: Icon }) => {
            const off = kind === "image" && ed.imagesFull;
            return (
              <button key={kind} type="button" className="ed-btn" disabled={off} onClick={() => ed.onPick(i, j, kind)}
                title={off ? t("imagesFull", { max: limits.images }) : undefined}>
                <Icon size={13} weight="bold" />{t(`field.${kind}`)}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** The small buttons under a list or table that add an item, a row or a column. */
function Grow({ items }: { items: { what: "item" | "row" | "col"; path: string; full: boolean; label: string; limit: string }[] }) {
  const ed = useContext(PageEdit);
  if (!ed) return null;
  return (
    <div className="ed-only ed-grow">
      {items.map((x) => (
        <button key={x.what} type="button" className="ed-btn" disabled={x.full} onClick={() => ed.onGrow(x.path, x.what)}
          title={x.full ? x.limit : undefined}>
          <Plus size={12} weight="bold" />{x.label}
        </button>
      ))}
    </div>
  );
}

/** The button over a chart or map that opens its data, shown while the pointer is on it. */
function DataButton({ p }: { p: string }) {
  const t = useTranslations("tools.pages");
  const ed = useContext(PageEdit);
  if (!ed) return null;
  return <button type="button" className="ed-btn ed-over ed-only" onClick={() => ed.onData(p)}>{t("editData")}</button>;
}

/** A picture, while it is drawn anew the old one stays dimmed under a note. */
function Picture({ src, alt, p, imageBase }: { src: string; alt: string; p: string; imageBase: string }) {
  const t = useTranslations("tools.pages");
  const ed = useContext(PageEdit);
  const old = ed?.pending.get(src);
  const drawing = old !== undefined;
  const shown = drawing ? old : src;
  return (
    <div className={`pic${drawing ? " drawing" : ""}`}>
      {shown ? (
        // eslint-disable-next-line @next/next/no-img-element -- served by our own route behind the session
        <img src={`${imageBase}/${shown}`} alt={alt} />
      ) : <div className="pic-empty" />}
      {drawing && <div className="pic-note"><Spinner size="sm" color="current" />{t("drawing")}</div>}
      {ed && !drawing && (
        <button type="button" className="ed-btn ed-over ed-only" onClick={() => ed.onImage(p)}>{t("redraw")}</button>
      )}
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
      {s.layout && (
        <Select<Heading> size="sm" value={s.heading ?? "top"} ariaLabel={t("headingLabel")} onChange={(h) => edit.onHeading(i, h)}
          options={HEADINGS.map((h) => ({ value: h, label: t(`headings.${h}`) }))} />
      )}
    </div>
  );
}

/** The fixed parts of a page carry these ids, every other section belongs to the subject. */
const FRAME_IDS = new Set(["cover", "gist", "map", "words"]);
const isContent = (s: Section) => !s.hero && !FRAME_IDS.has(s.id);

interface SectionProps {
  design: Design;
  /** Its number among the subject's sections, absent for the frame. */
  chapter?: number;
  s: Section;
  i: number;
  n: number;
  limits: Limits;
  imageBase: string;
  nums: Map<string, number>;
  edit?: EditControls | null;
  /** The page's picture stands as a section of its own above the title. */
  hasCover?: boolean;
}

/** A long title gets a smaller size, so it never breaks into a tower of single words. */
const titleSize = (title: string) =>
  (title.length > 48 ? " t-xl" : title.length > 26 ? " t-l" : "")
  // A very long word would break in the middle on a phone, the title shrinks there instead.
  + (Math.max(...title.split(/\s+/).map((w) => w.length)) > 13 ? " t-word" : "");

function SectionView({ s, i, n, limits, imageBase, nums, edit, design, chapter, hasCover }: SectionProps) {
  const t = useTranslations("tools.pages");
  const p = `sections.${i}`;
  const cls = s.hidden ? " is-hidden" : "";
  if (s.hero) {
    const j = s.blocks.findIndex((b) => b.kind === "image");
    const img = j >= 0 ? (s.blocks[j] as Extract<Block, { kind: "image" }>) : null;
    const figure = img && (
      <figure className="img" data-d={`${p}.blocks.${j}`}>
        <Picture src={img.src} alt={img.alt} p={`${p}.blocks.${j}`} imageBase={imageBase} />
      </figure>
    );
    return (
      <section id={s.id} className={`hero${titleSize(s.title)}${cls}`} data-i={i}>
        {edit && <Tools s={s} i={i} n={n} edit={edit} />}
        {/* An older page keeps its picture inside the title, it runs wide above the text there too. */}
        {figure}
        <div className="hero-text">
          <Txt path={`${p}.title`} value={s.title} as="h1" max={limits.short} />
          <Txt path={`${p}.lead`} value={s.lead} as="p" className="lead" max={limits.long} />
          <Txt path={`${p}.meta`} value={s.meta} as="p" className="meta" max={limits.long} />
        </div>
        {edit && !img && !hasCover && (
          <div className="ed-only ed-hero-add">
            <button type="button" className="ed-btn" disabled={edit.imagesFull} onClick={() => edit.onHeroImage(i)}>
              <ImageIcon size={13} weight="bold" />{t("addHeroImage")}
            </button>
          </div>
        )}
      </section>
    );
  }
  if (s.layout) {
    // The owner places title and lead above, beside, below the fields or leaves them out.
    const heading: Heading = s.heading ?? "top";
    return (
      <section id={s.id} className={`${chapter != null ? "content" : "frame"} added h-${heading}${cls}`} data-i={i}>
        {edit && <Tools s={s} i={i} n={n} edit={edit} />}
        {heading !== "none" && <div className="txt">
          {design === "chapters" && chapter != null && (
            <span className="chap" aria-hidden="true">{String(chapter).padStart(2, "0")}</span>
          )}
          {design === "timeline" && chapter != null && <span className="tl-dot" aria-hidden="true" />}
          <Txt path={`${p}.title`} value={s.title} as="h2" max={limits.short} />
          <Txt path={`${p}.lead`} value={s.lead} as="p" className="lead" max={limits.long} />
        </div>}
        <div className="body">
          <div className={`lay lay-${s.layout}`}>
            {s.blocks.map((b, j) => (b.kind === "empty" ? <EmptyField key={j} i={i} j={j} limits={limits} /> : (
              <div className="fld blk" data-d={`${p}.blocks.${j}`} key={j}>
                <BlockView b={b} p={`${p}.blocks.${j}`} limits={limits} imageBase={imageBase} num={nums.get(`${i}.${j}`)} />
              </div>
            )))}
          </div>
        </div>
      </section>
    );
  }
  const blocks = s.blocks.map((b, j) => (
    <div className={`blk k-${b.kind}`} data-d={`${p}.blocks.${j}`} key={j}>
      <BlockView b={b} p={`${p}.blocks.${j}`} limits={limits} imageBase={imageBase} num={nums.get(`${i}.${j}`)} />
    </div>
  ));
  // An image sits beside one short block, a long one would turn into a narrow column. The magazine turns every second pair.
  const other = s.blocks.find((b) => b.kind !== "image");
  const short = !!other && (other.kind === "text" ? other.text.length <= 500
    : other.kind === "bullets" ? other.items.length <= 4 : other.kind === "figures");
  const duo = s.blocks.length === 2 && s.blocks.some((b) => b.kind === "image") && short;
  const even = chapter != null && chapter % 2 === 0;
  const flip = design === "magazine" && even;
  const band = design === "magazine" && even ? " band" : "";
  return (
    <section id={s.id} className={`${chapter != null ? "content" : "frame"}${s.id === "cover" ? " cover" : ""}${band}${cls}`} data-i={i}>
      {edit && <Tools s={s} i={i} n={n} edit={edit} />}
      <div className="txt">
        {design === "chapters" && chapter != null && (
          <span className="chap" aria-hidden="true">{String(chapter).padStart(2, "0")}</span>
        )}
        {design === "timeline" && chapter != null && <span className="tl-dot" aria-hidden="true" />}
        <Txt path={`${p}.title`} value={s.title} as="h2" max={limits.short} />
        <Txt path={`${p}.lead`} value={s.lead} as="p" className="lead" max={limits.long} />
      </div>
      <div className="body">{duo ? <div className={`duo${flip ? " flip" : ""}`}>{blocks}</div> : blocks}</div>
    </section>
  );
}

function Caption({ p, b, num, kind, limits }: { p: string; b: { caption: string }; num?: number; kind: "figure" | "table"; limits: Limits }) {
  const t = useTranslations("tools.pages");
  const { editing } = useContext(EditCtx);
  const words = CAPTION_WORDS[useContext(PageLang)];
  if (num == null || (!b.caption && !editing)) return null;
  return (
    <figcaption>
      <b>{words ? `${words[kind]} ${num}` : t(kind, { n: num })}</b>
      <Txt path={`${p}.caption`} value={b.caption} max={limits.short} />
    </figcaption>
  );
}

function BlockView({ b, p, limits, imageBase, num }: { b: Block; p: string; limits: Limits; imageBase: string; num?: number }) {
  const fmt = useNumber();
  const t = useTranslations("tools.pages");
  const S = limits.short, I = limits.item;
  switch (b.kind) {
    case "empty":
      return null;
    case "text":
      return <Txt path={`${p}.text`} value={b.text} as="p" className="prose" max={limits.long} />;
    case "bullets":
      return (
        <>
          <ul className="bul">
            {b.items.map((v, i) => (
              <li key={i} data-d={`${p}.items.${i}`}><Txt path={`${p}.items.${i}`} value={v} as="div" max={I} /></li>
            ))}
          </ul>
          <Grow items={[{ what: "item", path: p, full: b.items.length >= limits.items, label: t("addItem"), limit: t("maxItems", { max: limits.items }) }]} />
        </>
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
      // A sign that every card carries says nothing, so the block shows signs only when they differ.
      const signs = new Set(b.cards.map((c) => (ICONS[c.icon] ? c.icon : "none")));
      const showSigns = signs.size > 1;
      return (
        <div className="panel">
          <div className={`grid g${cols}`}>
            {b.cards.map((c, i) => {
              const Icon = showSigns ? ICONS[c.icon] : undefined;
              return (
                <div className="cell" key={i} data-d={`${p}.cards.${i}`}>
                  {Icon && <div className={`ic ${c.icon}`}><Icon size={18} weight="bold" aria-hidden="true" /></div>}
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
        <div className="panel has-over">
          <DataButton p={p} />
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
                  <tr>{b.header.map((h, i) => <th key={i}><Txt path={`${p}.header.${i}`} value={h} as="div" max={S} keep /></th>)}</tr>
                </thead>
                <tbody>
                  {b.rows.map((r, i) => (
                    <tr key={i} data-d={`${p}.rows.${i}`}>
                      {r.map((c, j) => (
                        <td key={j} data-label={j ? b.header[j] : undefined}>
                          <Txt path={`${p}.rows.${i}.${j}`} value={c} as="div" max={S} keep />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Grow items={[
              { what: "row", path: p, full: b.rows.length >= limits.tableRows, label: t("addRow"), limit: t("maxRows", { max: limits.tableRows }) },
              { what: "col", path: p, full: b.header.length >= limits.tableCols, label: t("addCol"), limit: t("maxCols", { max: limits.tableCols }) },
            ]} />
          </div>
          <Caption p={p} b={b} num={num} kind="table" limits={limits} />
        </figure>
      );
    case "image":
      return (
        <figure className="img">
          <Picture src={b.src} alt={b.alt} p={p} imageBase={imageBase} />
          <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
        </figure>
      );
    case "chart":
      return (
        <figure>
          <div className="panel has-over">
            <DataButton p={p} />
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
          <div className="panel has-over">
            <DataButton p={p} />
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
          <div className="panel has-over"><DataButton p={p} /><WordCloud b={b} /></div>
          <Caption p={p} b={b} num={num} kind="figure" limits={limits} />
        </figure>
      );
  }
}
