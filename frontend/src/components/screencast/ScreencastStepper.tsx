"use client";

import { useTranslations } from "next-intl";
import SchrittReiter from "@/components/tools/SchrittReiter";
import type { ScreencastStep } from "@/types";
import { istErreichbar, nieBetretbar, STEP_KEYS, stepToIndex, vorherErreichbar } from "./steps";

interface ScreencastStepperProps {
  step: ScreencastStep;
  maxReachedIdx: number;
  skipTranslation: boolean;
  hatErgebnis?: boolean;
  onStepClick: (index: number) => void;
  /** Discards the whole screencast, absent where there is nothing to discard. */
  onDiscard?: (() => void) | null;
  discardLabel?: string;
}

/** The shared step tabs with the screencast's eight steps, the skipped translation struck through. */
export default function ScreencastStepper({
  step,
  maxReachedIdx,
  skipTranslation,
  hatErgebnis = false,
  onStepClick,
  onDiscard,
  discardLabel,
}: ScreencastStepperProps) {
  const t = useTranslations("stepper");
  const current = stepToIndex(step);
  return (
    <SchrittReiter
      labels={STEP_KEYS.map((key) => t(`steps.${key}`))}
      current={current}
      canEnter={(i) => istErreichbar(i, maxReachedIdx, skipTranslation, step, hatErgebnis)}
      isClosedForGood={(i) => nieBetretbar(i, skipTranslation)}
      isSkipped={(i) => skipTranslation && i === 1}
      backIndex={vorherErreichbar(current, maxReachedIdx, skipTranslation, step, hatErgebnis)}
      onStepClick={onStepClick}
      onDiscard={onDiscard}
      discardLabel={discardLabel}
    />
  );
}
