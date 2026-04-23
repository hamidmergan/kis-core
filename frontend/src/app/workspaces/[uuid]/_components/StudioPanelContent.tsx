"use client";

import React from "react";
import dynamic from "next/dynamic";
import Spinner from "@/components/ui/Spinner";
import { ExerciseSetsOverview } from "./ExerciseSetsOverview";
import { StudioOverview } from "./StudioOverview";
import type {
  ExerciseSet,
  SprachtrainingView,
  StudentStats,
  StudioView,
  Source,
} from "../_types";
import type { Note } from "./NotizenStudio";
import type { useMindmap } from "../_hooks/useMindmap";
import type { useDatentabelle } from "../_hooks/useDatentabelle";

const loader = () => <div className="flex-1 flex items-center justify-center p-6"><Spinner size="md" /></div>;

const NotizenStudio = dynamic(() => import("./NotizenStudio").then((m) => ({ default: m.NotizenStudio })), { loading: loader, ssr: false });
const DatentabelleStudio = dynamic(() => import("./DatentabelleStudio").then((m) => ({ default: m.DatentabelleStudio })), { loading: loader, ssr: false });
const MindmapStudio = dynamic(() => import("./MindmapStudio").then((m) => ({ default: m.MindmapStudio })), { loading: loader, ssr: false });
const LernkartenLearnView = dynamic(() => import("./LernkartenLearnView").then((m) => ({ default: m.LernkartenLearnView })), { loading: loader, ssr: false });
const MCExerciseView = dynamic(() => import("./MCExerciseView").then((m) => ({ default: m.MCExerciseView })), { loading: loader, ssr: false });

interface ExerciseBundle {
  exerciseSets: ExerciseSet[];
  activeSet: ExerciseSet | null;
  setActiveSet: (s: ExerciseSet | null) => void;
  loadExerciseSet: (id: number) => Promise<void>;
  deleteExerciseSet: (id: number, tool: string) => void;
  downloadExerciseSet: (s: ExerciseSet) => void;
  setCreateSetTool: (t: string) => void;
  setShowCreateModal: (v: boolean) => void;
  submitSingleAnswer: (setId: number, itemId: number, correct: boolean, newRun?: boolean) => void;
}

interface NotesBundle {
  notes: Note[];
  addNote: (content: string, sourceUuids?: string[]) => void;
  deleteNote: (id: number) => void;
  updateNoteTitle: (id: number, title: string | null) => void;
  pendingTitleIds: Set<number>;
}

type MindmapBundle = ReturnType<typeof useMindmap>;
type DatentabelleBundle = ReturnType<typeof useDatentabelle>;

interface StudioPanelContentProps {
  // View-Zustand
  studioView: StudioView;
  setStudioView: (v: StudioView) => void;
  sprachView: SprachtrainingView;
  sprachtrainingActive: boolean;
  studioTabRequest: { tab: "tools" | "glossar" | "notizen" | "statistik" | "zeitplan"; nonce: number } | null;
  // Content-Slots
  sprachtrainingContent: React.ReactNode;
  glossarContent: React.ReactNode;
  notizenContent: React.ReactNode;
  // Domain-Bundles
  exercises: ExerciseBundle;
  notes: NotesBundle;
  mindmap: MindmapBundle;
  datentabelle: DatentabelleBundle;
  // Kontext
  moduleUuid: string;
  statsVersion: number;
  sources: Source[];
  selectedSourceIds: string[];
  isAdmin: boolean;
  pageStats: StudentStats | null;
  // Callbacks
  onStudioSelect: (v: StudioView) => void;
  onNavigateToSet: (setId: number, tool: string, mode: string) => void;
  onSprachNavigate: (v: SprachtrainingView) => void;
  onAskChat: (text: string, switchTab?: boolean) => void;
  onPillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
  refreshProgress: () => void;
  // Panel-Kontext
  onMinimize: () => void;
  hideHeader: boolean;
}

export function StudioPanelContent(props: StudioPanelContentProps) {
  const {
    studioView, setStudioView, sprachView, sprachtrainingActive, studioTabRequest,
    sprachtrainingContent, glossarContent, notizenContent,
    exercises: ex, notes: nt, mindmap: mm, datentabelle: dt,
    moduleUuid, statsVersion, sources, selectedSourceIds, isAdmin, pageStats,
    onStudioSelect, onNavigateToSet, onSprachNavigate, onAskChat, onPillClick,
    refreshProgress, onMinimize, hideHeader,
  } = props;

  if (sprachView !== "overview") return <>{sprachtrainingContent}</>;

  if (studioView === "overview") {
    return (
      <StudioOverview
        onSelect={onStudioSelect}
        onMinimize={onMinimize}
        sprachtrainingActive={sprachtrainingActive}
        sprachtrainingContent={sprachtrainingContent}
        glossarContent={glossarContent}
        notizenContent={notizenContent}
        moduleUuid={moduleUuid}
        statsVersion={statsVersion}
        onNavigateToSet={onNavigateToSet}
        onSprachNavigate={onSprachNavigate}
        activeSourceCount={selectedSourceIds.length}
        sprachView={sprachView}
        requestedTab={studioTabRequest}
        sources={sources}
        selectedSourceIds={selectedSourceIds}
        onPillClick={onPillClick}
        {...(hideHeader ? { hideHeader: true } : {})}
      />
    );
  }

  const { activeSet, setActiveSet, exerciseSets, loadExerciseSet, deleteExerciseSet, downloadExerciseSet, setCreateSetTool, setShowCreateModal, submitSingleAnswer } = ex;

  const onSourceClick = (filename: string, page: number, startTime?: number, highlightText?: string) => {
    const src = sources.find((s) => s.filename === filename);
    if (src) onPillClick(src.uuid, page, filename, highlightText, startTime);
  };

  if (activeSet && activeSet.tool === "karteikarten") {
    return (
      <LernkartenLearnView
        exerciseSet={activeSet}
        onBack={() => { setActiveSet(null); refreshProgress(); }}
        onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
        onAskChat={(text) => onAskChat(text, hideHeader)}
        onSourceClick={onSourceClick}
        breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: "Karteikarten", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
      />
    );
  }

  if (activeSet && activeSet.tool === "quiz") {
    return (
      <MCExerciseView
        exerciseSet={activeSet}
        tool="quiz"
        onBack={() => { setActiveSet(null); refreshProgress(); }}
        onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
        onAskChat={(text) => onAskChat(text, true)}
        onSourceClick={onSourceClick}
        breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: "Quiz", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
      />
    );
  }

  const setsCrumb = [{ label: "Studio", onClick: () => setStudioView("overview") }];

  if (studioView === "karteikarten") {
    return (
      <ExerciseSetsOverview
        title="Karteikarten"
        sets={exerciseSets.filter((s) => s.tool === "karteikarten")}
        onBack={() => setStudioView("overview")}
        onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
        onCreate={() => { setCreateSetTool("karteikarten"); setShowCreateModal(true); }}
        onDelete={(id) => deleteExerciseSet(id, "karteikarten")}
        onDownload={isAdmin ? downloadExerciseSet : undefined}
        sourceCount={selectedSourceIds.length}
        stats={pageStats}
        breadcrumbs={setsCrumb}
      />
    );
  }

  if (studioView === "notizen") {
    return (
      <NotizenStudio
        notes={nt.notes}
        onAdd={nt.addNote}
        onDelete={nt.deleteNote}
        onUpdateTitle={nt.updateNoteTitle}
        onBack={() => setStudioView("overview")}
        sources={sources}
        activeSourceIds={selectedSourceIds}
        onPillClick={onPillClick}
        stats={pageStats}
        breadcrumbs={setsCrumb}
        pendingTitleIds={nt.pendingTitleIds}
      />
    );
  }

  if (studioView === "datentabelle") {
    return (
      <DatentabelleStudio
        table={dt.datentabelle}
        sources={dt.datentabelleSources}
        loading={dt.datentabelleLoading}
        onGenerate={dt.generate}
        onBack={() => setStudioView("overview")}
        savedList={dt.datentabelleList}
        onSelect={dt.select}
        onDelete={dt.remove}
        sourceCount={selectedSourceIds.length}
        allSources={sources}
        onPillClick={onPillClick}
        stats={pageStats}
        breadcrumbs={setsCrumb}
      />
    );
  }

  if (studioView === "mindmap") {
    return (
      <MindmapStudio
        mindmap={mm.mindmapData}
        loading={mm.mindmapLoading}
        onGenerate={mm.generate}
        onBack={() => setStudioView("overview")}
        savedList={mm.mindmapList}
        onSelect={mm.select}
        onDelete={mm.remove}
        sourceCount={selectedSourceIds.length}
        sources={sources}
        onPillClick={onPillClick}
        stats={pageStats}
        breadcrumbs={setsCrumb}
      />
    );
  }

  if (studioView === "quiz") {
    return (
      <ExerciseSetsOverview
        title="Quiz"
        sets={exerciseSets.filter((s) => s.tool === "quiz")}
        onBack={() => setStudioView("overview")}
        onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
        onCreate={() => { setCreateSetTool("quiz"); setShowCreateModal(true); }}
        onDelete={(id) => deleteExerciseSet(id, "quiz")}
        onDownload={isAdmin ? downloadExerciseSet : undefined}
        sourceCount={selectedSourceIds.length}
        stats={pageStats}
        breadcrumbs={setsCrumb}
      />
    );
  }

  return null;
}
