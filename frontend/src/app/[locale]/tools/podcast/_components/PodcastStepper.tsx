"use client";

import { useTranslations } from "next-intl";
import SchrittReiter from "@/components/tools/SchrittReiter";
import { STEPS, type Step } from "../_types";

interface PodcastStepperProps {
  step: Step;
  canEnter: (index: number) => boolean;
  isClosedForGood: (index: number) => boolean;
  onStepClick: (index: number) => void;
}

/** The shared step tabs with the podcast's five steps. */
export default function PodcastStepper({ step, canEnter, isClosedForGood, onStepClick }: PodcastStepperProps) {
  const t = useTranslations("tools.podcast.steps");
  return (
    <SchrittReiter labels={STEPS.map((key) => t(key))} current={STEPS.indexOf(step)} canEnter={canEnter}
                   isClosedForGood={isClosedForGood} onStepClick={onStepClick} />
  );
}
