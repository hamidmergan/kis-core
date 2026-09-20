"use client";

import { ArrowDown, ArrowUp, CaretDown, Image as ImageIcon, Plus, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import HelpTooltip from "@/components/ui/HelpTooltip";
import IconButton from "@/components/ui/IconButton";
import StatusMark from "@/components/ui/StatusMark";
import { MAX_NOTES, type Slide } from "../_types";

interface FolienKarteProps {
  index: number;
  slide: Slide;
  previewUrl: string | null;
  imageMissing: boolean;
  notesOn: boolean;
  first: boolean;
  last: boolean;
  open: boolean;
  onToggle: () => void;
  onChange: (slide: Slide) => void;
  onMove: (delta: -1 | 1) => void;
  onDelete: () => void;
  onInsertAfter: () => void;
  onRegenText: () => void;
  onRegenImage: () => void;
  onAnchor: (text: string) => void;
  onOpenPreview: () => void;
}

// Like FIELD, but without a resting border so the note reads as plain text on the row.
// No hover border either, the whole row already lights up under the pointer.
const NOTIZ =
  "w-full px-3 py-2 text-sm border-2 border-transparent rounded-md bg-background focus:outline-none focus:border-kb";

/** One slide as a register row: number and role in the margin, the title on the line,
 *  preview and speaker notes inside. */
export default function FolienKarte(p: FolienKarteProps) {
  const t = useTranslations("tools.praesentation.slides");
  const s = p.slide;
  const fest = s.role === "deckblatt" || s.role === "abschluss";
  const hatBild = s.images.length > 0 || s.body?.kind === "image";

  const vorschau = (
    <button type="button" onClick={p.onOpenPreview} aria-label={t("openPreview", { n: p.index + 1 })}
            className={`block w-full rounded-md overflow-hidden bg-surface cursor-zoom-in leading-none hover:brightness-[0.98] transition-[filter] ${p.notesOn ? "sm:w-80 sm:shrink-0" : "sm:max-w-xl"}`}>
      {p.previewUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={p.previewUrl} alt="" className="block w-full h-auto" />
      ) : (
        // Without a preview the placeholder keeps 16:9, otherwise the row jumps in
        // height the moment the image arrives.
        <span className="aspect-video text-xs text-muted flex items-center justify-center">{t("noPreview")}</span>
      )}
    </button>
  );

  const knoepfe = (
    <div className="flex flex-wrap gap-1">
      {hatBild && <IconButton size="sm" aria-label={t("regenImage")} onClick={p.onRegenImage}><ImageIcon className="w-3 h-3" /></IconButton>}
      <IconButton size="sm" aria-label={t("up")} disabled={p.first} onClick={() => p.onMove(-1)}><ArrowUp className="w-3 h-3" /></IconButton>
      <IconButton size="sm" aria-label={t("down")} disabled={p.last} onClick={() => p.onMove(1)}><ArrowDown className="w-3 h-3" /></IconButton>
      <IconButton size="sm" aria-label={t("insertAfter")} disabled={s.role === "abschluss"} onClick={p.onInsertAfter}><Plus className="w-3 h-3" /></IconButton>
      <IconButton size="sm" aria-label={t("delete")} disabled={fest} onClick={p.onDelete}><Trash className="w-3 h-3" /></IconButton>
    </div>
  );

  return (
    <li className={`folien-zeile ${p.open ? "offen" : ""}`}>
      <button type="button" onClick={p.onToggle} aria-expanded={p.open} aria-controls={`folie-panel-${p.index}`}
              className="folien-kopf py-3.5 text-[0.9375rem]">
        <span className="folien-rand">
          <span className="text-sm font-medium whitespace-nowrap">{t("slideLabel", { n: p.index + 1 })}</span>
          <span className="text-3xs uppercase tracking-wide text-muted whitespace-nowrap">{t(`roles.${s.role}`)}</span>
          {p.imageMissing && <StatusMark tone="warn">{t("imageMissing")}</StatusMark>}
        </span>
        <span className="folien-titel truncate">{s.title}</span>
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
                  <textarea className={`${NOTIZ} mt-1 resize-y`} rows={7} value={s.notes} maxLength={MAX_NOTES} aria-label={t("notes")}
                            onChange={(e) => p.onChange({ ...s, notes: e.target.value })} />
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
