import React from "react";
import { useTranslations } from "next-intl";
import type { ExerciseItem } from "../../_types";
import { _chunkLabel, _getChipIcon } from "../../_utils";
import { sourceTag } from "./SetSourceLegend";
import { itemSources } from "./_itemSources";

/** The source chips under an exercise, they only navigate like chat citations. */
export function ItemSourceChips({ card, numbers, onSourceClick, firstPageDefault = false }: {
  card: ExerciseItem;
  numbers: Parameters<typeof sourceTag>[1];
  onSourceClick?: (filename: string, page: number, startTime?: number, claim?: string) => void;
  // Flashcards name page one when the place carries no number.
  firstPageDefault?: boolean;
}) {
  const tChip = useTranslations("sourceChip");
  const srcs = itemSources(card);
  if (!srcs.length) return null;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1 flex-wrap">
        {srcs.map((s, si) => {
          const ChipIcon = _getChipIcon(s.source_label);
          return (
            <button key={si} type="button"
              onClick={() => { if (onSourceClick) onSourceClick(s.source_label, s.page_number ?? 1, s.start_time, s.highlight_text || `${card.front} ${card.back}`); }}
              className="chip-cite inline-flex items-center gap-0.5 text-3xs font-medium px-2 py-1 rounded-full border-none cursor-pointer transition-colors"
              style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
              <ChipIcon size={10} weight="bold" /> {sourceTag(s.source_label, numbers)}{_chunkLabel(s.source_label, firstPageDefault ? s.page_number ?? 1 : s.page_number, s.start_time, (key, vals) => tChip(key, vals))}
            </button>
          );
        })}
      </div>
    </div>
  );
}
