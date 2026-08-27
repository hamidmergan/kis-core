"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { CaretDown } from "@phosphor-icons/react";
import { _getChipIcon } from "../../_utils";
import type { ExerciseSetSource } from "../../_types";

/** The numbered source list, the numbers belong to the set. */

/** filename -> the number the legend gives it. Missing file means no bracket. */
export function sourceNumbers(sources?: ExerciseSetSource[] | null): Record<string, number> {
  const out: Record<string, number> = {};
  for (const s of sources || []) out[s.filename] = s.number;
  return out;
}

/** A bracket only when there is something to tell apart. */
export function sourceTag(filename: string, numbers: Record<string, number>): string {
  if (Object.keys(numbers).length < 2) return "";
  const n = numbers[filename];
  return n ? `[${n}] ` : "";
}

export function SetSourceLegend({
  sources, onSourceClick, className = "",
}: {
  sources?: ExerciseSetSource[] | null;
  onSourceClick?: (filename: string) => void;
  className?: string;
}) {
  const t = useTranslations("workspace.detail.languageTraining.common");
  /** Collapsed as the initial state, the row stays visible. */
  const [open, setOpen] = useState(false);

  if (!sources || sources.length === 0) return null;
  /** The list is a footnote and reads like one. */
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-xs leading-snug text-left min-w-0 hover-lighten transition-colors"
        style={{ color: "var(--muted)" }}
      >
        <CaretDown
          size={12}
          weight="bold"
          className="shrink-0 transition-transform"
          style={{ transform: open ? "none" : "rotate(-90deg)" }}
        />
        <span className="truncate">{t("sourcesToggle", { count: sources.length })}</span>
      </button>

      {open && sources.map((s) => {
        const Icon = _getChipIcon(s.filename);
        return (
          <button
            key={s.number}
            type="button"
            onClick={() => onSourceClick?.(s.filename)}
            disabled={!onSourceClick}
            className="flex items-center gap-1.5 pl-4 text-xs leading-snug text-left min-w-0 disabled:cursor-default hover-lighten transition-colors"
            style={{ color: "var(--muted)" }}
          >
            <Icon size={13} weight="regular" className="shrink-0" />
            <span className="shrink-0">[{s.number}]</span>
            <span className="truncate">{s.filename}</span>
          </button>
        );
      })}
    </div>
  );
}
