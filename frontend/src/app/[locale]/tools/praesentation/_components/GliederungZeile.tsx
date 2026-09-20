"use client";

import { ArrowDown, ArrowUp, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import IconButton from "@/components/ui/IconButton";
import { FIELD } from "./VorlageHochladen";
import { MAX_GIST, type OutlineRow } from "../_types";

interface GliederungZeileProps {
  index: number;
  row: OutlineRow;
  first: boolean;
  last: boolean;
  onChange: (row: OutlineRow) => void;
  onMove: (delta: -1 | 1) => void;
  onDelete: () => void;
  onAnchor: (text: string) => void;
}

/** One planned slide: number, role tag, editable title and gist, the three actions. */
export default function GliederungZeile({ index, row, first, last, onChange, onMove, onDelete, onAnchor }: GliederungZeileProps) {
  const t = useTranslations("tools.praesentation.outline");
  const fest = row.role === "deckblatt" || row.role === "abschluss";
  return (
    <li className="flex gap-3 items-start rounded-xl border border-border p-3">
      <span className="rounded-full flex items-center justify-center text-xs font-bold shrink-0 w-7 h-7 bg-surface text-muted-soft">{index + 1}</span>
      <div className="flex-1 min-w-0">
        <span className="text-3xs uppercase tracking-wide text-muted">{t(`roles.${row.role}`)}</span>
        <input className={`${FIELD} mt-1 font-medium`} value={row.title} maxLength={120}
               aria-label={t("titleAria", { n: index + 1 })}
               onChange={(e) => onChange({ ...row, title: e.target.value })} />
        <textarea className={`${FIELD} mt-2 resize-none`} rows={2} value={row.gist} maxLength={MAX_GIST}
                  aria-label={t("gistAria", { n: index + 1 })}
                  onMouseUp={() => onAnchor(window.getSelection()?.toString().trim() || "")}
                  onChange={(e) => onChange({ ...row, gist: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1 shrink-0">
        <IconButton size="sm" aria-label={t("up")} disabled={first} onClick={() => onMove(-1)}><ArrowUp className="w-3 h-3" /></IconButton>
        <IconButton size="sm" aria-label={t("down")} disabled={last} onClick={() => onMove(1)}><ArrowDown className="w-3 h-3" /></IconButton>
        <IconButton size="sm" aria-label={t("delete")} disabled={fest} onClick={onDelete}><Trash className="w-3 h-3" /></IconButton>
      </div>
    </li>
  );
}
