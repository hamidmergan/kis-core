"use client";

import { useCallback, useEffect } from "react";
import type { SprachtrainingView, StudioView } from "../_types";

interface UseStudioNavigationOptions {
  studioView: StudioView;
  setStudioView: (v: StudioView) => void;
  setSprachView: (v: SprachtrainingView) => void;
  loadExerciseSets: (tool?: string) => void;
  loadExerciseSet: (id: number) => Promise<void>;
  selectMindmap: (id: number) => void;
  selectDatentabelle: (id: number) => void;
  loadStreak: () => void;
  bumpStats: () => void;
}

export function useStudioNavigation(opts: UseStudioNavigationOptions) {
  const {
    studioView, setStudioView, setSprachView,
    loadExerciseSets, loadExerciseSet, selectMindmap, selectDatentabelle,
    loadStreak, bumpStats,
  } = opts;

  // Load exercise sets when switching to quiz studio view
  useEffect(() => {
    if (studioView === "quiz") loadExerciseSets("quiz");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studioView]);

  const handleStudioSelect = useCallback((view: StudioView) => {
    if (view === "karteikarten" || view === "quiz") loadExerciseSets(view);
    setStudioView(view);
  }, [loadExerciseSets, setStudioView]);

  const handleNavigateToSet = useCallback((setId: number, tool: string, mode: string) => {
    if (tool === "mindmap") {
      selectMindmap(setId);
      setStudioView("mindmap");
      return;
    }
    if (tool === "datentabelle") {
      selectDatentabelle(setId);
      setStudioView("datentabelle");
      return;
    }
    loadExerciseSet(setId).then(() => {
      if (tool === "lernkarten" || (tool === "karteikarten" && mode === "glossar")) setSprachView("lk-learn");
      else if (tool === "lueckentext") setSprachView("cl-learn");
      else if (tool === "vokabeltest") setSprachView("vt-learn");
      else setStudioView(tool as StudioView);
    });
  }, [selectMindmap, selectDatentabelle, loadExerciseSet, setSprachView, setStudioView]);

  const handleSprachNavigate = useCallback((view: SprachtrainingView) => {
    if (view === "lk-sets") loadExerciseSets("lernkarten");
    if (view === "cl-sets") loadExerciseSets("lueckentext");
    if (view === "vt-sets") loadExerciseSets("vokabeltest");
    setSprachView(view);
  }, [loadExerciseSets, setSprachView]);

  const refreshProgress = useCallback(() => {
    loadStreak();
    loadExerciseSets();
    bumpStats();
  }, [loadStreak, loadExerciseSets, bumpStats]);

  return { handleStudioSelect, handleNavigateToSet, handleSprachNavigate, refreshProgress };
}
