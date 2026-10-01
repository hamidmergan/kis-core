"use client";

import { useTranslations } from "next-intl";
import SchrittReiter from "@/components/tools/SchrittReiter";
import { STEPS, type Step } from "../_types";

interface PraesentationStepperProps {
  step: Step;
  canEnter: (index: number) => boolean;
  /** A step that can never be entered again, shown faded. */
  isClosedForGood: (index: number) => boolean;
  onStepClick: (index: number) => void;
  /** Discards the whole run, absent where there is nothing to discard. */
  onDiscard?: (() => void) | null;
}

/** The shared step tabs with the presentation's three steps. */
export default function PraesentationStepper({ step, canEnter, isClosedForGood, onStepClick, onDiscard }: PraesentationStepperProps) {
  const t = useTranslations("tools.praesentation.steps");
  const tPage = useTranslations("tools.praesentation");
  return (
    <SchrittReiter labels={STEPS.map((key) => t(key))} current={STEPS.indexOf(step)} canEnter={canEnter}
                   isClosedForGood={isClosedForGood} onStepClick={onStepClick} onDiscard={onDiscard} discardLabel={tPage("discard")} />
  );
}
