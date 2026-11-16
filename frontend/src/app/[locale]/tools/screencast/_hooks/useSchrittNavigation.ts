"use client";

import { useCallback, useEffect, type Dispatch } from "react";
import { indexToStep, istErreichbar, stepToIndex, vorherErreichbar } from "@/components/screencast/steps";
import type { ScreencastStep } from "@/types";
import type { FlowAction } from "../_reducer";

interface Optionen {
  step: ScreencastStep;
  maxReachedIdx: number;
  skipTranslation: boolean;
  hatErgebnis: boolean;
  dispatch: Dispatch<FlowAction>;
}

/** The stepper clicks and the way back of each page, the same for the tool and its demo. */
export function useSchrittNavigation({ step, maxReachedIdx, skipTranslation, hatErgebnis, dispatch }: Optionen) {
  // Every step entered counts as reached, so the stepper lets the person return to it.
  useEffect(() => {
    dispatch({ type: "ADVANCE_REACHED", idx: stepToIndex(step) });
  }, [step, dispatch]);

  const gotoIndex = useCallback((index: number) => {
    const target = indexToStep(index);
    if (target) dispatch({ type: "SET_STEP", step: target });
  }, [dispatch]);

  const handleStepClick = useCallback((index: number) => {
    if (!istErreichbar(index, maxReachedIdx, skipTranslation, step, hatErgebnis)) return;
    gotoIndex(index);
  }, [gotoIndex, maxReachedIdx, skipTranslation, step, hatErgebnis]);

  /** The step back from a page, or null when nothing enterable lies before it. */
  const zurueckVon = useCallback((index: number): (() => void) | null => {
    const ziel = vorherErreichbar(index, maxReachedIdx, skipTranslation, step, hatErgebnis);
    return ziel === null ? null : () => gotoIndex(ziel);
  }, [gotoIndex, maxReachedIdx, skipTranslation, step, hatErgebnis]);

  return { handleStepClick, zurueckVon };
}
