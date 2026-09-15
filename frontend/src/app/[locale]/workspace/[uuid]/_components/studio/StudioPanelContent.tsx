"use client";

import React from "react";
import { useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import Spinner from "@/components/ui/Spinner";
import { ExerciseSetsOverview } from "../language_training/ExerciseSetsOverview";
import { StudioOverview } from "./StudioOverview";
import type {
  ExerciseSet,
  LanguageTrainingView,
  StudioView,
  Source,
} from "../../_types";
import type { Note } from "./NotesStudio";
import type { useMindmap } from "../../_hooks/useMindmap";
import type { useDataTable } from "../../_hooks/useDataTable";

const loader = () => <div className="flex-1 flex items-center justify-center p-6"><Spinner size="md" /></div>;

const NotesStudio = dynamic(() => import("./NotesStudio").then((m) => ({ default: m.NotesStudio })), { loading: loader, ssr: false });
const DataTableStudio = dynamic(() => import("./DataTableStudio").then((m) => ({ default: m.DataTableStudio })), { loading: loader, ssr: false });
const MindmapStudio = dynamic(() => import("./MindmapStudio").then((m) => ({ default: m.MindmapStudio })), { loading: loader, ssr: false });
const FlashcardsLearnView = dynamic(() => import("../language_training/FlashcardsLearnView").then((m) => ({ default: m.FlashcardsLearnView })), { loading: loader, ssr: false });
const MCExerciseView = dynamic(() => import("../language_training/MCExerciseView").then((m) => ({ default: m.MCExerciseView })), { loading: loader, ssr: false });

interface ExerciseBundle {
  exerciseSets: ExerciseSet[];
  activeSet: ExerciseSet | null;
  setActiveSet: (s: ExerciseSet | null) => void;
  loadExerciseSet: (id: number) => Promise<void>;
  deleteExerciseSet: (id: number, tool: string) => void;
  renameExerciseSet: (id: number, tool: string, title: string) => Promise<void>;
  retryExerciseSet: (id: number, tool: string) => void;
  downloadExerciseSet: (s: ExerciseSet) => void;
  setCreateSetTool: (t: string) => void;
  setShowCreateModal: (v: boolean) => void;
  submitSingleAnswer: (setId: number, itemId: number, correct: boolean, newRun: boolean) => void;
}

interface NotesBundle {
  notes: Note[];
  addNote: (content: string, sourceUuids?: string[], options?: { autoTitle?: boolean }) => void;
  deleteNote: (id: number) => void;
  updateNoteTitle: (id: number, title: string | null) => void;
  pendingTitleIds: Set<number>;
}

type MindmapBundle = ReturnType<typeof useMindmap>;
type DataTableBundle = ReturnType<typeof useDataTable>;

interface StudioPanelContentProps {
  // View-Zustand
  studioView: StudioView;
  setStudioView: (v: StudioView) => void;
  langTrainingView: LanguageTrainingView;
  language_trainingActive: boolean;
  studioTabRequest: { tab: "tools" | "glossary" | "notes" | "statistik" | "schedule"; nonce: number } | null;
  onStudioTabRequestHandled: () => void;
  // Content-Slots
  language_trainingContent: React.ReactNode;
  glossaryContent: React.ReactNode;
  notesContent: React.ReactNode;
  // Domain-Bundles
  exercises: ExerciseBundle;
  notes: NotesBundle;
  mindmap: MindmapBundle;
  data_table: DataTableBundle;
  // Kontext
  workspaceUuid: string;
  statsVersion: number;
  sources: Source[];
  selectedSourceIds: string[];
  isAdmin: boolean;
  // Callbacks
  onStudioSelect: (v: StudioView) => void;
  onNavigateToSet: (setId: number, tool: string, mode: string) => void;
  onSprachNavigate: (v: LanguageTrainingView) => void;
  onAskChat: (text: string, switchTab?: boolean) => void;
  onPillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
  refreshProgress: () => void;
  // Shortcut: jump straight into viewer mode instead of the list
  openMindmapInViewer: boolean;
  consumeMindmapViewerOpen: () => void;
  openDataTableInViewer: boolean;
  consumeDataTableViewerOpen: () => void;
  // Panel-Kontext
  onMinimize: () => void;
  hideHeader: boolean;
  chatLang: "de" | "en";
}

export function StudioPanelContent(props: StudioPanelContentProps) {
  const t = useTranslations("workspace.detail.studio");
  const {
    studioView, setStudioView, langTrainingView, language_trainingActive, studioTabRequest, onStudioTabRequestHandled,
    language_trainingContent, glossaryContent, notesContent,
    exercises: ex, notes: nt, mindmap: mm, data_table: dt,
    workspaceUuid, statsVersion, sources, selectedSourceIds, isAdmin,
    onStudioSelect, onNavigateToSet, onSprachNavigate, onAskChat, onPillClick,
    refreshProgress, onMinimize, hideHeader, chatLang,
    openMindmapInViewer, consumeMindmapViewerOpen,
    openDataTableInViewer, consumeDataTableViewerOpen,
  } = props;

  if (langTrainingView !== "overview") return <>{language_trainingContent}</>;

  if (studioView === "overview") {
    return (
      <StudioOverview
        onSelect={onStudioSelect}
        onMinimize={onMinimize}
        language_trainingActive={language_trainingActive}
        language_trainingContent={language_trainingContent}
        glossaryContent={glossaryContent}
        notesContent={notesContent}
        workspaceUuid={workspaceUuid}
        statsVersion={statsVersion}
        onNavigateToSet={onNavigateToSet}
        onSprachNavigate={onSprachNavigate}
        activeSourceCount={selectedSourceIds.length}
        langTrainingView={langTrainingView}
        requestedTab={studioTabRequest}
        onRequestedTabHandled={onStudioTabRequestHandled}
        sources={sources}
        selectedSourceIds={selectedSourceIds}
        onPillClick={onPillClick}
        {...(hideHeader ? { hideHeader: true } : {})}
      />
    );
  }

  const { activeSet, setActiveSet, exerciseSets, loadExerciseSet, deleteExerciseSet, renameExerciseSet, retryExerciseSet, downloadExerciseSet, setCreateSetTool, setShowCreateModal, submitSingleAnswer } = ex;

  const onSourceClick = (filename: string, page: number, startTime?: number) => {
    // Tool chips only jump, only a selection of your own is highlighted.
    const src = sources.find((s) => s.filename === filename);
    if (src) onPillClick(src.uuid, page, filename, undefined, startTime, false);
  };

  if (activeSet && activeSet.tool === "karteikarten") {
    return (
      <FlashcardsLearnView
        exerciseSet={activeSet}
        onBack={() => { setActiveSet(null); refreshProgress(); }}
        onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
        onAskChat={(text) => onAskChat(text, hideHeader)}
        onSourceClick={onSourceClick}
        breadcrumbs={[{ label: t("panelTitle"), onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: t("tiles.karteikarten"), toolKey: "Flashcards", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
        chatLang={chatLang}
        workspaceUuid={workspaceUuid}
      />
    );
  }

  if (activeSet && activeSet.tool === "quiz") {
    return (
      <MCExerciseView
        exerciseSet={activeSet}
        onBack={() => { setActiveSet(null); refreshProgress(); }}
        onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
        onAskChat={(text) => onAskChat(text, true)}
        onSourceClick={onSourceClick}
        breadcrumbs={[{ label: t("panelTitle"), onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: t("tiles.quiz"), toolKey: "Quiz", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
        chatLang={chatLang}
      />
    );
  }

  const setsCrumb = [{ label: t("panelTitle"), onClick: () => setStudioView("overview") }];

  if (studioView === "karteikarten") {
    return (
      <ExerciseSetsOverview
        title={t("tiles.karteikarten")}
        toolKey="Flashcards"
        sets={exerciseSets.filter((s) => s.tool === "karteikarten")}
        onBack={() => setStudioView("overview")}
        onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
        onCreate={() => { setCreateSetTool("karteikarten"); setShowCreateModal(true); }}
        onDelete={(id) => deleteExerciseSet(id, "karteikarten")}
        onRename={(id, title) => renameExerciseSet(id, "karteikarten", title)}
        onRetry={(id) => retryExerciseSet(id, "karteikarten")}
        onDownload={isAdmin ? downloadExerciseSet : undefined}
        sourceCount={selectedSourceIds.length}
        breadcrumbs={setsCrumb}
      />
    );
  }

  if (studioView === "notes") {
    return (
      <NotesStudio
        notes={nt.notes}
        onAdd={(content) => nt.addNote(content, undefined, { autoTitle: false })}
        onDelete={nt.deleteNote}
        onUpdateTitle={nt.updateNoteTitle}
        onBack={() => setStudioView("overview")}
        sources={sources}
        activeSourceIds={selectedSourceIds}
        onPillClick={onPillClick}
        breadcrumbs={setsCrumb}
        pendingTitleIds={nt.pendingTitleIds}
      />
    );
  }

  if (studioView === "data_table") {
    return (
      <DataTableStudio
        table={dt.data_table}
        sources={dt.data_tableSources}
        loading={dt.data_tableLoading}
        onGenerate={dt.generate}
        onBack={() => setStudioView("overview")}
        savedList={dt.data_tableList}
        onSelect={dt.select}
        onDelete={dt.remove}
        onRename={dt.rename}
        sourceCount={selectedSourceIds.length}
        allSources={sources}
        onPillClick={onPillClick}
        breadcrumbs={setsCrumb}
        openInViewer={openDataTableInViewer}
        onViewerOpened={consumeDataTableViewerOpen}
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
        onRename={mm.rename}
        sourceCount={selectedSourceIds.length}
        sources={sources}
        pickedSources={mm.mindmapSources}
        onPillClick={onPillClick}
        breadcrumbs={setsCrumb}
        openInViewer={openMindmapInViewer}
        onViewerOpened={consumeMindmapViewerOpen}
      />
    );
  }

  if (studioView === "quiz") {
    return (
      <ExerciseSetsOverview
        title={t("tiles.quiz")}
        toolKey="Quiz"
        sets={exerciseSets.filter((s) => s.tool === "quiz")}
        onBack={() => setStudioView("overview")}
        onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
        onCreate={() => { setCreateSetTool("quiz"); setShowCreateModal(true); }}
        onDelete={(id) => deleteExerciseSet(id, "quiz")}
        onRename={(id, title) => renameExerciseSet(id, "quiz", title)}
        onRetry={(id) => retryExerciseSet(id, "quiz")}
        onDownload={isAdmin ? downloadExerciseSet : undefined}
        sourceCount={selectedSourceIds.length}
        breadcrumbs={setsCrumb}
      />
    );
  }

  return null;
}
