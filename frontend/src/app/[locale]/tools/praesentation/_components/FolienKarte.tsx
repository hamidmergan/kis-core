"use client";

import { ArrowDown, ArrowUp, CaretDown, Image as ImageIcon, Plus, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import HelpTooltip from "@/components/ui/HelpTooltip";
import IconButton from "@/components/ui/IconButton";
import StatusMark from "@/components/ui/StatusMark";
import { Balken } from "./FolienSkizze";
import { MAX_NOTES, type Slide } from "../_types";

interface FolienKarteProps {
  index: number;
  /** Null for a placeholder row while the outline is still being planned. */
  role: string | null;
  /** The planned title until the slide is written, empty while nothing is known yet. */
  titel: string;
  /** Null while its text is still being written. */
  slide: Slide | null;
  previewUrl: string | null;
  /** Stands where the preview goes while the slide is written or redone. */
  skizze: ReactNode;
  imageMissing: boolean;
  notesOn: boolean;
  first: boolean;
  last: boolean;
  open: boolean;
  /** While a run goes on every edit waits, the server would refuse it anyway. */
  gesperrt: boolean;
  onToggle: () => void;
  onChange: (slide: Slide) => void;
  onMove: (delta: -1 | 1) => void;
  onDelete: () => void;
  onInsertAfter: () => void;
  onRegenImage: () => void;
  onAnchor: (text: string) => void;
  onOpenPreview: () => void;
}

// Like FIELD, but without a resting border so the note reads as plain text on the row.
// No hover border either, the whole row already lights up under the pointer.
const NOTIZ =
  "w-full px-3 py-2 text-sm border-2 border-transparent rounded-md bg-background focus:outline-none focus:border-kb";

/** One slide as a register row: number and role in the margin, the title on the line,
 *  preview and speaker notes inside, a skeleton until the run has written them. */
export default function FolienKarte(p: FolienKarteProps) {
  const t = useTranslations("tools.praesentation.slides");
  const s = p.slide;
  const fest = p.role === "deckblatt" || p.role === "abschluss";
  const hatBild = !!s && (s.images.length > 0 || s.body?.kind === "image");
  const breite = p.notesOn ? "sm:w-80 sm:shrink-0" : "sm:max-w-xl";

  const vorschau = p.previewUrl ? (
    <button type="button" onClick={p.onOpenPreview} aria-label={t("openPreview", { n: p.index + 1 })}
            className={`block w-full rounded-md overflow-hidden bg-surface cursor-zoom-in leading-none hover:brightness-[0.98] transition-[filter] ${breite}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={p.previewUrl} alt="" className="block w-full h-auto animate-[fadeIn_0.3s_ease-out]" />
    </button>
  ) : (
    <div className={`w-full ${breite}`}>{p.skizze}</div>
  );

  const knoepfe = p.role !== null && (
    <div className="flex flex-wrap gap-1">
      {hatBild && <IconButton size="sm" aria-label={t("regenImage")} disabled={p.gesperrt} onClick={p.onRegenImage}><ImageIcon className="w-3 h-3" /></IconButton>}
      <IconButton size="sm" aria-label={t("up")} disabled={p.first || p.gesperrt} onClick={() => p.onMove(-1)}><ArrowUp className="w-3 h-3" /></IconButton>
      <IconButton size="sm" aria-label={t("down")} disabled={p.last || p.gesperrt} onClick={() => p.onMove(1)}><ArrowDown className="w-3 h-3" /></IconButton>
      <IconButton size="sm" aria-label={t("insertAfter")} disabled={p.role === "abschluss" || p.gesperrt} onClick={p.onInsertAfter}><Plus className="w-3 h-3" /></IconButton>
      <IconButton size="sm" aria-label={t("delete")} disabled={fest || p.gesperrt} onClick={p.onDelete}><Trash className="w-3 h-3" /></IconButton>
    </div>
  );

  return (
    <li className={`folien-zeile ${p.open ? "offen" : ""}`}>
      <button type="button" onClick={p.onToggle} aria-expanded={p.open} aria-controls={`folie-panel-${p.index}`}
              className="folien-kopf py-3.5 text-[0.9375rem]">
        <span className="folien-rand">
          <span className="text-sm font-medium whitespace-nowrap">{t("slideLabel", { n: p.index + 1 })}</span>
          {p.role
            ? <span className="text-3xs uppercase tracking-wide text-muted whitespace-nowrap">{t(`roles.${p.role}`)}</span>
            : <Balken laeuft={p.gesperrt} className="w-12 mt-1" />}
          {p.imageMissing && <StatusMark tone="warn">{t("imageMissing")}</StatusMark>}
        </span>
        {p.titel
          ? <span className="folien-titel truncate">{p.titel}</span>
          : <span className="folien-titel"><Balken laeuft={p.gesperrt} className="h-3 w-1/2" /></span>}
        <span className="row-caret" aria-hidden="true">
          <CaretDown size={14} weight="bold" className={`transition-transform ${p.open ? "rotate-180" : ""}`} />
        </span>
      </button>

      {p.open && (
        <div id={`folie-panel-${p.index}`} className="pb-4 animate-[fadeIn_0.2s_ease-out]">
          {/* With notes the preview stands beside them, without notes it takes the freed
              width and the buttons drop underneath, so no area stays empty. items-start
              keeps the preview from being stretched to the height of the note. */}
          {p.notesOn ? (
            <div className="flex flex-col sm:flex-row sm:items-start gap-4">
              {vorschau}
              <div className="flex-1 min-w-0 flex flex-col gap-3.5">
                <div onMouseUp={() => p.onAnchor(window.getSelection()?.toString().trim() || "")}>
                  <span className="flex items-center gap-1.5 text-sm font-medium">
                    {t("notes")}
                    {p.index === 0 && <HelpTooltip text={t("notesHelp")} />}
                  </span>
                  {s ? (
                    <textarea className={`${NOTIZ} mt-1 resize-y`} rows={7} value={s.notes} maxLength={MAX_NOTES} aria-label={t("notes")}
                              readOnly={p.gesperrt}
                              onChange={(e) => p.onChange({ ...s, notes: e.target.value })} />
                  ) : (
                    // The notes are written together with the text, until then they stand as grey lines.
                    <div className="mt-3 px-3 space-y-2">
                      <Balken laeuft={p.gesperrt} className="w-11/12" />
                      <Balken laeuft={p.gesperrt} className="w-full" />
                      <Balken laeuft={p.gesperrt} className="w-4/5" />
                      <Balken laeuft={p.gesperrt} className="w-2/3" />
                    </div>
                  )}
                </div>
                {knoepfe}
              </div>
            </div>
          ) : (
            // Without notes nothing stands beside the preview, so the pair sits in the middle
            // instead of clinging to the left edge with a wide empty strip on the right.
            <div className="flex flex-col items-center gap-4">
              {vorschau}
              {knoepfe}
            </div>
          )}
        </div>
      )}
    </li>
  );
}
