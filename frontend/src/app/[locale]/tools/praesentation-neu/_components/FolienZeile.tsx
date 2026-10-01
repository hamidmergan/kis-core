"use client";

import { useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, CaretDown, Image as ImageIcon, Plus, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import HelpTooltip from "@/components/ui/HelpTooltip";
import IconButton from "@/components/ui/IconButton";
import StatusMark from "@/components/ui/StatusMark";
import { Balken } from "../../praesentation/_components/FolienSkizze";
import { MAX_NOTES, type Slide } from "../../praesentation/_types";

interface Props {
  index: number;
  /** Null for a placeholder row while the outline is still being planned. */
  role: string | null;
  titel: string;
  slide: Slide | null;
  previewUrl: string | null;
  skizze: ReactNode;
  imageMissing: boolean;
  notesOn: boolean;
  first: boolean;
  last: boolean;
  open: boolean;
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
const NOTIZ =
  "w-full px-3 py-2 text-sm border-2 border-transparent rounded-md bg-background focus:outline-none focus:border-kb";

/** One slide as a register row, the preview with its actions on the left and the notes on the right. */
export default function FolienZeile(p: Props) {
  const t = useTranslations("tools.praesentation.slides");
  const tNeu = useTranslations("tools.praesentation.neu");
  // On the phone the note stays folded until asked for, the preview comes first.
  const [notizMobil, setNotizMobil] = useState(false);
  const s = p.slide;
  const fest = p.role === "deckblatt" || p.role === "abschluss";
  const art = s?.body && s.body.kind !== "bullets" ? s.body.kind : null;
  const hatBild = !!s && (s.images.length > 0 || s.body?.kind === "image");

  const vorschau = p.previewUrl ? (
    <button type="button" onClick={p.onOpenPreview} aria-label={t("openPreview", { n: p.index + 1 })}
            className="block w-full rounded-md overflow-hidden border border-border-soft bg-surface shadow-sm cursor-zoom-in leading-none hover:brightness-[0.98] transition-[filter]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={p.previewUrl} alt="" className="block w-full h-auto animate-[fadeIn_0.3s_ease-out]" />
    </button>
  ) : (
    <div className="w-full">{p.skizze}</div>
  );

  const knoepfe = p.role !== null && (
    <div className="flex flex-wrap gap-1.5">
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
            ? <span className="text-3xs uppercase tracking-wide text-muted whitespace-nowrap">{t(art ? `kinds.${art}` : `roles.${p.role}`)}</span>
            : <Balken laeuft={p.gesperrt} className="w-12 mt-1" />}
        </span>
        <span className="folien-titel flex items-center gap-2.5 min-w-0">
          {p.titel ? <span className="truncate">{p.titel}</span> : <Balken laeuft={p.gesperrt} className="h-3 w-1/2" />}
          {p.imageMissing && <StatusMark tone="warn" className="text-2xs shrink-0">{t("imageMissing")}</StatusMark>}
        </span>
        <span className="row-caret" aria-hidden="true">
          <CaretDown size={14} weight="bold" className={`transition-transform ${p.open ? "rotate-180" : ""}`} />
        </span>
      </button>

      {p.open && (
        <div id={`folie-panel-${p.index}`} className="pb-4 animate-[fadeIn_0.2s_ease-out]">
          <div className={`flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-6 ${p.notesOn ? "" : "sm:justify-center"}`}>
            <div className={`flex flex-col gap-2.5 w-full ${p.notesOn ? "sm:w-80 sm:shrink-0" : "sm:max-w-xl"}`}>
              {vorschau}
              <div className="flex items-center justify-between gap-2">
                {knoepfe}
                {p.notesOn && s && (
                  <button type="button" onClick={() => setNotizMobil((x) => !x)} aria-expanded={notizMobil}
                          className="sm:hidden text-xs text-kb underline">
                    {tNeu("editNote")}
                  </button>
                )}
              </div>
            </div>
            {p.notesOn && (
              <div className={`flex-1 min-w-0 ${notizMobil ? "block" : "hidden"} sm:block`}
                   onMouseUp={() => p.onAnchor(window.getSelection()?.toString().trim() || "")}>
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  {t("notes")}
                  {p.index === 0 && <HelpTooltip text={t("notesHelp")} />}
                </span>
                {s ? (
                  <textarea className={`${NOTIZ} mt-1.5 resize-y`} rows={7} value={s.notes} maxLength={MAX_NOTES} aria-label={t("notes")}
                            readOnly={p.gesperrt} onChange={(e) => p.onChange({ ...s, notes: e.target.value })} />
                ) : (
                  <div className="mt-3 px-3 space-y-2">
                    <Balken laeuft={p.gesperrt} className="w-11/12" />
                    <Balken laeuft={p.gesperrt} className="w-full" />
                    <Balken laeuft={p.gesperrt} className="w-4/5" />
                    <Balken laeuft={p.gesperrt} className="w-2/3" />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </li>
  );
}
