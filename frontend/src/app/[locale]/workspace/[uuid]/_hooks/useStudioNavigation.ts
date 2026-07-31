"use client";

import { useCallback, useEffect, useState } from "react";
import type { LanguageTrainingView, StudioView } from "../_types";

interface UseStudioNavigationOptions {
  studioView: StudioView;
  setStudioView: (v: StudioView) => void;
  setSprachView: (v: LanguageTrainingView) => void;
  loadExerciseSets: (tool?: string) => void;
  loadExerciseSet: (id: number) => Promise<void>;
  selectMindmap: (id: number) => void;
  selectDataTable: (id: number) => void;
  loadStreak: () => void;
  bumpStats: () => void;
}

export function useStudioNavigation(opts: UseStudioNavigationOptions) {
  const {
    studioView, setStudioView, setSprachView,
    loadExerciseSets, loadExerciseSet, selectMindmap, selectDataTable,
    loadStreak, bumpStats,
  } = opts;

  const [openMindmapInViewer, setOpenMindmapInViewer] = useState(false);
  const [openDataTableInViewer, setOpenDataTableInViewer] = useState(false);

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
      setOpenMindmapInViewer(true);
      setStudioView("mindmap");
      return;
    }
    if (tool === "data_table") {
      selectDataTable(setId);
      setOpenDataTableInViewer(true);
      setStudioView("data_table");
      return;
    }
    loadExerciseSet(setId).then(() => {
      if (tool === "flashcards" || (tool === "karteikarten" && mode === "glossary")) setSprachView("lk-learn");
      else if (tool === "grammatik") setSprachView("gr-learn");
      else if (tool === "hoerverstehen") setSprachView("hv-learn");
      else setStudioView(tool as StudioView);
    });
  }, [selectMindmap, selectDataTable, loadExerciseSet, setSprachView, setStudioView]);

  const handleSprachNavigate = useCallback((view: LanguageTrainingView) => {
    if (view === "lk-sets") loadExerciseSets("flashcards");
    if (view === "gr-sets") loadExerciseSets("grammatik");
    if (view === "hv-sets") loadExerciseSets("hoerverstehen");
    setSprachView(view);
  }, [loadExerciseSets, setSprachView]);

  const refreshProgress = useCallback(() => {
    loadStreak();
    loadExerciseSets();
    bumpStats();
  }, [loadStreak, loadExerciseSets, bumpStats]);

  const consumeMindmapViewerOpen = useCallback(() => setOpenMindmapInViewer(false), []);
  const consumeDataTableViewerOpen = useCallback(() => setOpenDataTableInViewer(false), []);

  return {
    handleStudioSelect, handleNavigateToSet, handleSprachNavigate, refreshProgress,
    openMindmapInViewer, consumeMindmapViewerOpen,
    openDataTableInViewer, consumeDataTableViewerOpen,
  };
}
