"use client";

import { _getChipIcon } from "../../_utils";
import type { ExerciseSetSource } from "../../_types";

/**
 * The numbered source list under an exercise set, and the numbering its citation
 * chips print.
 *
 * Numbering belongs to the SET, not to the card on screen. Numbering per card gave
 * one file different numbers on different cards, which makes the bracket useless as
 * a reference. The order is the one the learner picked the sources in and comes from
 * the backend, so it survives a reload and matches between the list and the exercises.
 */

/** filename -> the number the legend gives it. Missing file means no bracket. */
export function sourceNumbers(sources?: ExerciseSetSource[] | null): Record<string, number> {
  const out: Record<string, number> = {};
  for (const s of sources || []) out[s.filename] = s.number;
  return out;
}

/** "[3] " for a file that is in the legend, "" for one that is not.
 *  Single-source sets get no bracket at all: there is nothing to tell apart. */
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
  if (!sources || sources.length === 0) return null;
  /* Size: the list is a footnote and reads as one. text-xs sits under the exercise
     text without dropping to the 10px floor, and nothing in it is bold, so the
     numbers do not fight the exercises for attention (Ansage vom 2026-08-05).
     The icon follows the text, otherwise it shrinks to a dot next to it. */
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {sources.map((s) => {
        const Icon = _getChipIcon(s.filename);
        return (
          <button
            key={s.number}
            type="button"
            onClick={() => onSourceClick?.(s.filename)}
            disabled={!onSourceClick}
            className="flex items-center gap-1.5 text-xs leading-snug text-left min-w-0 disabled:cursor-default hover-lighten transition-colors"
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
