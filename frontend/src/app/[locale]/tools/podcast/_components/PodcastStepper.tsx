"use client";

import { useTranslations } from "next-intl";
import SchrittReiter from "@/components/tools/SchrittReiter";
import { STEPS, type Step } from "../_types";

interface PodcastStepperProps {
  step: Step;
  canEnter: (index: number) => boolean;
  isClosedForGood: (index: number) => boolean;
  onStepClick: (index: number) => void;
  /** Discards the whole podcast, absent where there is nothing to discard. */
  onDiscard?: (() => void) | null;
}

/** The shared step tabs with the podcast's five steps. */
export default function PodcastStepper({ step, canEnter, isClosedForGood, onStepClick, onDiscard }: PodcastStepperProps) {
  const t = useTranslations("tools.podcast.steps");
  const tTool = useTranslations("tools.podcast");
  return (
    <SchrittReiter labels={STEPS.map((key) => t(key))} current={STEPS.indexOf(step)} canEnter={canEnter}
                   isClosedForGood={isClosedForGood} onStepClick={onStepClick} onDiscard={onDiscard} discardLabel={tTool("discardPodcast")} />
  );
}
