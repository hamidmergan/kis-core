"use client";

import { useTranslations } from "next-intl";
import SchrittReiter from "@/components/tools/SchrittReiter";
import type { ScreencastStep } from "@/types";
import { istErreichbar, nieBetretbar, STEP_KEYS, stepToIndex } from "./steps";

interface ScreencastStepperProps {
  step: ScreencastStep;
  maxReachedIdx: number;
  skipTranslation: boolean;
  hatErgebnis?: boolean;
  onStepClick: (index: number) => void;
}

/** The shared step tabs with the screencast's eight steps, the skipped translation struck through. */
export default function ScreencastStepper({
  step,
  maxReachedIdx,
  skipTranslation,
  hatErgebnis = false,
  onStepClick,
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
      onStepClick={onStepClick}
    />
  );
}
