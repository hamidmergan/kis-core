"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import { HEADINGS, LAYOUTS, type Block, type Heading, type Layout, type Limits } from "../_lib/types";

const FIELD = "px-3 py-1.5 text-sm border-2 border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft";
const LAYOUT_KEYS: Record<Layout, string> = {
  "1": "one", "2": "two", "21": "wideNarrow", "12": "narrowWide", "3": "three", "4": "four", "1-2": "oneTwo",
};
// The columns of each sketch, the same proportions the page draws.
const SKETCH: Record<Layout, string> = {
  "1": "1fr", "2": "1fr 1fr", "21": "2fr 1fr", "12": "1fr 2fr", "3": "1fr 1fr 1fr", "4": "1fr 1fr", "1-2": "1fr 1fr",
};

function Footer({ onCancel, onOk, ok, busy, disabled }: { onCancel: () => void; onOk?: () => void; ok?: string; busy?: boolean; disabled?: boolean }) {
  const t = useTranslations("tools.pages");
  return (
    <div className="flex justify-end gap-2">
      <button type="button" className="px-4 py-2 text-sm btn-secondary rounded-lg" onClick={onCancel}>{t("cancel")}</button>
      {onOk && (
        <button type="button" className="px-4 py-2 text-sm btn-primary rounded-lg flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={onOk} disabled={busy || disabled}>
          {busy && <Spinner size="sm" color="current" />}{ok}
        </button>
      )}
    </div>
  );
}

// Where the title bar sits in each sketch, as grid areas around the fields.
const HEAD_SKETCH: Record<Heading, { cols: string; rows: string; areas: string } | null> = {
  top: { cols: "1fr", rows: "10px 1fr", areas: '"h" "f"' },
  bottom: { cols: "1fr", rows: "1fr 10px", areas: '"f" "h"' },
  left: { cols: "28% 1fr", rows: "1fr", areas: '"h f"' },
  right: { cols: "1fr 28%", rows: "1fr", areas: '"f h"' },
  none: null,
};

/** The fields of a grid as a small sketch, with the title bar where it will stand. */
function Sketch({ l, heading }: { l: Layout; heading: Heading }) {
  const head = HEAD_SKETCH[heading];
  const fields = (
    <span className="grid gap-1 h-full" style={{ gridTemplateColumns: SKETCH[l], gridArea: "f" }}>
      {Array.from({ length: LAYOUTS[l] }, (_, i) => (
        <i key={i} className="rounded" style={{ background: "var(--surface-dim)", gridColumn: l === "1-2" && i === 0 ? "1 / -1" : undefined }} />
      ))}
    </span>
  );
  if (!head) return <span className="block h-[52px]" aria-hidden="true">{fields}</span>;
  return (
    <span className="grid gap-1 h-[52px]" style={{ gridTemplateColumns: head.cols, gridTemplateRows: head.rows, gridTemplateAreas: head.areas }} aria-hidden="true">
      <i className="rounded" style={{ background: "var(--kb60)", gridArea: "h" }} />
      {fields}
    </span>
  );
}

/** The choice of a grid for a new section and of where its title stands, each drawn as a small sketch. */
export function LayoutModal({ open, left, onClose, onPick }: { open: boolean; left: number; onClose: () => void; onPick: (l: Layout, h: Heading) => void }) {
  const t = useTranslations("tools.pages");
  const [heading, setHeading] = useState<Heading>("top");
  return (
    <Modal open={open} onClose={onClose} size="md" title={t("addSection")} footer={<Footer onCancel={onClose} />}>
      <p className="text-sm mb-3" style={{ color: "var(--muted)" }}>{t("layoutHint", { left })}</p>
      <p className="text-sm font-medium text-foreground mb-1.5">{t("headingLabel")}</p>
      <div className="flex flex-wrap gap-1.5 mb-4" role="radiogroup" aria-label={t("headingLabel")}>
        {HEADINGS.map((h) => (
          <button key={h} type="button" role="radio" aria-checked={heading === h} onClick={() => setHeading(h)}
            className={`px-3 py-1 text-xs font-medium rounded-lg border-2 transition-colors ${heading === h ? "border-kb bg-kb text-white" : "border-border-soft bg-background hover:border-kb"}`}>
            {t(`headings.${h}`)}
          </button>
        ))}
      </div>
      <p className="text-sm font-medium text-foreground mb-1.5">{t("layoutLabel")}</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
        {(Object.keys(LAYOUTS) as Layout[]).map((l) => (
          <button key={l} type="button" onClick={() => onPick(l, heading)}
            className="flex flex-col gap-2 p-2.5 text-left text-xs font-medium rounded-lg border-2 border-border-soft bg-background hover:border-kb focus-visible:border-kb focus-visible:outline-none transition-colors">
            <Sketch l={l} heading={heading} />
            {t(`layouts.${LAYOUT_KEYS[l]}`)}
          </button>
        ))}
      </div>
    </Modal>
  );
}

/** The description of a picture: filled with the old one for a redraw, empty for a new picture. */
export function ImageModal({ open, isNew, prompt, suggesting, max, onClose, onDraw }: {
  open: boolean; isNew: boolean; prompt: string; suggesting?: boolean; max: number; onClose: () => void; onDraw: (prompt: string) => Promise<void>;
}) {
  const t = useTranslations("tools.pages");
  const [text, setText] = useState(prompt);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (open) { setText(prompt); setError(null); } }, [open, prompt]);
  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      await onDraw(text.trim());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} size="md" title={isNew ? t("draw") : t("redraw")}
      footer={<Footer onCancel={onClose} onOk={go} ok={t("generate")} busy={busy} disabled={!text.trim() || suggesting} />}>
      <label htmlFor="pages-image-prompt" className="block text-sm font-medium text-foreground mb-1">{t("imagePromptLabel")}</label>
      <textarea id="pages-image-prompt" value={text} onChange={(e) => setText(e.target.value)} rows={isNew ? 4 : 8} maxLength={max}
        placeholder={suggesting ? t("imageSuggesting") : t("imagePromptPlaceholder")} disabled={suggesting}
        className={`${FIELD} w-full py-2 resize-y disabled:opacity-60`} autoFocus />
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{isNew ? t("imagePromptHintNew") : t("imagePromptHint")}</p>
      {error && <p className="mt-2 text-sm text-error" role="alert">{error}</p>}
    </Modal>
  );
}

type DataBlock = Extract<Block, { kind: "chart" | "bars" | "mindmap" | "wordcloud" }>;

/** One row of the data table: its texts, its numbers and the button that removes it. */
function Row({ cells, onRemove, removable, removeLabel }: { cells: React.ReactNode[]; onRemove: () => void; removable: boolean; removeLabel: string }) {
  return (
    <div className="flex items-center gap-2">
      {cells}
      <button type="button" onClick={onRemove} disabled={!removable} aria-label={removeLabel} title={removeLabel}
        className="w-7 h-7 flex-shrink-0 flex items-center justify-center rounded-full btn-icon disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ backgroundColor: "var(--surface-dim)" }}>
        <X size={13} weight="bold" />
      </button>
    </div>
  );
}

const num = (v: string) => {
  const n = Number(v.replace(",", "."));
  return Number.isFinite(n) && n >= 0 ? n : 0;
};

/**
 * The data behind a chart, a bar list, a mind map or a word cloud, as a table of fields.
 * Numbers are taken as typed, the page draws them anew on apply.
 */
export function DataModal({ block, limits, onClose, onApply }: { block: DataBlock | null; limits: Limits; onClose: () => void; onApply: (b: DataBlock) => void }) {
  const t = useTranslations("tools.pages");
  const [b, setB] = useState<DataBlock | null>(block);
  useEffect(() => setB(block), [block]);
  if (!b) return <Modal open={false} onClose={onClose}><span /></Modal>;
  const set = (fn: (x: DataBlock) => void) => setB((old) => {
    const next = JSON.parse(JSON.stringify(old)) as DataBlock;
    fn(next);
    return next;
  });
  const remove = t("removeRow");
  const value = (v: number, on: (s: string) => void, label: string) => (
    <input key="v" className={`${FIELD} w-24 flex-shrink-0`} type="number" min={0} step="any" defaultValue={v} aria-label={label}
      onChange={(e) => on(e.target.value)} />
  );
  const text = (v: string, max: number, on: (s: string) => void, label: string, grow = true) => (
    <input key={label} className={`${FIELD} ${grow ? "flex-1 min-w-0" : "w-full"}`} value={v} maxLength={max} aria-label={label}
      onChange={(e) => on(e.target.value)} />
  );
  const add = (full: boolean, label: string, limit: string, on: () => void) => (
    <button type="button" onClick={on} disabled={full} title={full ? limit : undefined}
      className="self-start px-3 py-1 text-xs font-medium btn-secondary rounded-lg disabled:opacity-40 disabled:cursor-not-allowed">+ {label}</button>
  );

  let body: React.ReactNode = null;
  if (b.kind === "chart") {
    const two = b.series.length > 1;
    body = (
      <>
        <div className="grid sm:grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--muted)" }}>{t("xLabel")}
            {text(b.x_label, limits.short, (v) => set((x) => { (x as typeof b).x_label = v; }), t("xLabel"), false)}</label>
          <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--muted)" }}>{t("yLabel")}
            {text(b.y_label, limits.short, (v) => set((x) => { (x as typeof b).y_label = v; }), t("yLabel"), false)}</label>
        </div>
        {two && (
          <div className="grid sm:grid-cols-2 gap-2">
            {b.series.map((s, k) => (
              <label key={k} className="flex flex-col gap-1 text-xs" style={{ color: "var(--muted)" }}>{t("seriesName", { n: k + 1 })}
                {text(s.name, limits.short, (v) => set((x) => { (x as typeof b).series[k].name = v; }), t("seriesName", { n: k + 1 }), false)}</label>
            ))}
          </div>
        )}
        <div className="flex gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span className="flex-1">{t("dataLabel")}</span>
          {b.series.map((s, k) => <span key={k} className="w-24">{two ? s.name || t("seriesName", { n: k + 1 }) : t("dataValue")}</span>)}
          <span className="w-7" />
        </div>
        {b.categories.map((c, i) => (
          <Row key={`${b.categories.length}-${i}`} removable={b.categories.length > 2} removeLabel={remove}
            onRemove={() => set((x) => { const y = x as typeof b; y.categories.splice(i, 1); y.series.forEach((s) => s.values.splice(i, 1)); })}
            cells={[
              text(c, limits.label, (v) => set((x) => { (x as typeof b).categories[i] = v; }), `${t("dataLabel")} ${i + 1}`),
              ...b.series.map((s, k) => value(s.values[i], (v) => set((x) => { (x as typeof b).series[k].values[i] = num(v); }), `${t("dataValue")} ${i + 1}`)),
            ]} />
        ))}
        {add(b.categories.length >= limits.items, t("dataValue"), t("maxItems", { max: limits.items }),
          () => set((x) => { const y = x as typeof b; y.categories.push(t("newValue")); y.series.forEach((s) => s.values.push(1)); }))}
      </>
    );
  } else if (b.kind === "bars") {
    body = (
      <>
        {b.bars.map((r, i) => (
          <Row key={`${b.bars.length}-${i}`} removable={b.bars.length > 1} removeLabel={remove}
            onRemove={() => set((x) => { (x as typeof b).bars.splice(i, 1); })}
            cells={[
              text(r.label, limits.short, (v) => set((x) => { (x as typeof b).bars[i].label = v; }), `${t("dataLabel")} ${i + 1}`),
              value(r.value, (v) => set((x) => { (x as typeof b).bars[i].value = num(v); }), `${t("dataValue")} ${i + 1}`),
            ]} />
        ))}
        {add(b.bars.length >= limits.items, t("dataValue"), t("maxItems", { max: limits.items }),
          () => set((x) => { (x as typeof b).bars.push({ label: t("newValue"), value: 1, text: "" }); }))}
      </>
    );
  } else if (b.kind === "mindmap") {
    body = (
      <>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--muted)" }}>{t("center")}
          {text(b.center, limits.mapLabel, (v) => set((x) => { (x as typeof b).center = v; }), t("center"), false)}</label>
        <div className="flex gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span className="w-40">{t("branch")}</span><span className="flex-1">{t("leaves")}</span><span className="w-7" />
        </div>
        {b.branches.map((br, i) => (
          <Row key={`${b.branches.length}-${i}`} removable={b.branches.length > 2} removeLabel={remove}
            onRemove={() => set((x) => { (x as typeof b).branches.splice(i, 1); })}
            cells={[
              <span key="t" className="w-40 flex-shrink-0">{text(br.title, limits.mapLabel, (v) => set((x) => { (x as typeof b).branches[i].title = v; }), `${t("branch")} ${i + 1}`, false)}</span>,
              // Free typing, a comma just typed must stay, so the field keeps its own text.
              <input key="l" className={`${FIELD} flex-1 min-w-0`} defaultValue={br.leaves.join(", ")} aria-label={`${t("leaves")} ${i + 1}`}
                maxLength={limits.mapLabel * limits.leaves}
                onChange={(e) => {
                  const v = e.target.value;
                  set((x) => { (x as typeof b).branches[i].leaves = v.split(",").map((w) => w.trim()).filter(Boolean).slice(0, limits.leaves); });
                }} />,
            ]} />
        ))}
        {add(b.branches.length >= limits.branches, t("branch"), t("maxItems", { max: limits.branches }),
          () => set((x) => { (x as typeof b).branches.push({ title: t("newValue"), to: "", leaves: [] }); }))}
      </>
    );
  } else {
    body = (
      <>
        <div className="flex gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span className="flex-1">{t("word")}</span><span className="w-24">{t("weight")}</span><span className="w-7" />
        </div>
        {b.words.map(([w, n], i) => (
          <Row key={`${b.words.length}-${i}`} removable={b.words.length > 3} removeLabel={remove}
            onRemove={() => set((x) => { (x as typeof b).words.splice(i, 1); })}
            cells={[
              text(w, limits.mapLabel, (v) => set((x) => { (x as typeof b).words[i][0] = v; }), `${t("word")} ${i + 1}`),
              value(n, (v) => set((x) => { (x as typeof b).words[i][1] = Math.max(1, Math.round(num(v))); }), `${t("weight")} ${i + 1}`),
            ]} />
        ))}
        {add(b.words.length >= limits.words, t("word"), t("maxItems", { max: limits.words }),
          () => set((x) => { (x as typeof b).words.push([t("newValue"), 1]); }))}
      </>
    );
  }
  return (
    <Modal open={!!block} onClose={onClose} size="lg" title={t("editData")}
      footer={<Footer onCancel={onClose} onOk={() => onApply(b)} ok={t("apply")} />}>
      <div className="flex flex-col gap-2.5 max-h-[60vh] overflow-y-auto pr-1">{body}</div>
    </Modal>
  );
}
