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
      <IconButton size="lg" onClick={onPrev} disabled={index === 0}
        title={backLabel} aria-label={backLabel}
        className="disabled:opacity-30">
        <CaretLeft size={18} weight="bold" />
      </IconButton>
      {/* Feste Breite und Ziffern gleicher Laufweite: die Pfeile duerfen beim
          Blaettern nicht wandern, wenn aus der 9 eine 10 wird. */}
      <span className="text-sm font-semibold text-center tabular-nums" style={{ minWidth: 60 }}>
        {index + 1} / {total}
      </span>
      <IconButton size="lg" onClick={onNext} title={forwardLabel} aria-label={forwardLabel}>
        {isLast ? <Check size={18} weight="bold" /> : <CaretRight size={18} weight="bold" />}
      </IconButton>
    </div>
  );
}
