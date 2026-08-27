import React from "react";
import { CaretLeft, CaretRight, Check } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";

/** Back, counter, next in one row, shared by all exercise views. */
export function ExerciseNav({
  index, total, onPrev, onNext, backLabel, nextLabel, finishLabel,
}: {
  index: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
  backLabel: string;
  nextLabel: string;
  finishLabel: string;
}) {
  const isLast = index + 1 >= total;
  const forwardLabel = isLast ? finishLabel : nextLabel;
  return (
    <div className="flex items-center justify-center gap-3">
      <IconButton onClick={onPrev} disabled={index === 0}
        title={backLabel} aria-label={backLabel}
        className="disabled:opacity-30">
        <CaretLeft size={14} weight="bold" />
      </IconButton>
      {/* Feste Breite und Ziffern gleicher Laufweite: die Pfeile duerfen beim
          Blaettern nicht wandern, wenn aus der 9 eine 10 wird. */}
      <span className="text-xs font-semibold text-center tabular-nums" style={{ minWidth: 52 }}>
        {index + 1} / {total}
      </span>
      <IconButton onClick={onNext} title={forwardLabel} aria-label={forwardLabel}>
        {isLast ? <Check size={14} weight="bold" /> : <CaretRight size={14} weight="bold" />}
      </IconButton>
    </div>
  );
}
