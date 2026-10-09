"use client";

import { createContext, useContext } from "react";
import { useTranslations } from "next-intl";
import { Plus } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { Heading, Limits } from "../../_lib/types";
import { EditCtx, Txt } from "../Txt";

/** What an empty field of an added section can become. */
export type FieldKind = "text" | "image" | "table" | "chart" | "list" | "note";

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

/** The editor's controls for the blocks deep inside the page, null for every reader. */
export const PageEdit = createContext<EditControls | null>(null);

/** The language the page is written in, its fixed words follow it, not the reader's. */
export const PageLang = createContext("de");

type Words = Record<"figure" | "table" | "vs" | "wrong" | "right" | "situation" | "approach" | "result" | "both" | "high" | "low" | "before" | "after" | "step", string>;

// The fixed words a page draws itself, in the page's language.
const WORDS: { de: Words; en: Words } = {
  de: {
    figure: "Abbildung", table: "Tabelle", vs: "vs", wrong: "Falsch", right: "Richtig",
    situation: "Ausgangslage", approach: "Vorgehen", result: "Ergebnis", both: "Gemeinsam",
    high: "hoch", low: "gering", before: "Vorher", after: "Nachher", step: "Schritt",
  },
  en: {
    figure: "Figure", table: "Table", vs: "vs", wrong: "Wrong", right: "Right",
    situation: "Situation", approach: "Approach", result: "Result", both: "Shared",
    high: "high", low: "low", before: "Before", after: "After", step: "Step",
  },
};
export type PageWord = keyof Words;

/** The fixed words in the page's language, English for every language but German. */
export function usePageWords(): Words {
  return useContext(PageLang) === "de" ? WORDS.de : WORDS.en;
}

/** The numbered caption under a figure or table, absent when it has no number. */
export function Caption({ p, b, num, kind, limits }: { p: string; b: { caption: string }; num?: number; kind: "figure" | "table"; limits: Limits }) {
  const { editing } = useContext(EditCtx);
  const w = usePageWords();
  if (num == null || (!b.caption && !editing)) return null;
  return (
    <figcaption>
      <b>{`${w[kind]} ${num}`}</b>
      <Txt path={`${p}.caption`} value={b.caption} max={limits.short} />
    </figcaption>
  );
}

/** The small buttons under a list or table that add an item, a row or a column. */
export function Grow({ items }: { items: { what: "item" | "row" | "col"; path: string; full: boolean; label: string; limit: string }[] }) {
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
export function DataButton({ p }: { p: string }) {
  const t = useTranslations("tools.pages");
  const ed = useContext(PageEdit);
  if (!ed) return null;
  return <button type="button" className="ed-btn ed-over ed-only" onClick={() => ed.onData(p)}>{t("editData")}</button>;
}

/** A picture, while it is drawn anew the old one stays dimmed under a note. */
export function Picture({ src, alt, p, imageBase }: { src: string; alt: string; p: string; imageBase: string }) {
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
