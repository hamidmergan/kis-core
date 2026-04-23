"use client";

import React from "react";
import dynamic from "next/dynamic";
import Spinner from "@/components/ui/Spinner";
import { ExerciseSetsOverview } from "./ExerciseSetsOverview";
import { ExerciseCompletion } from "./ExerciseCompletion";

const loader = () => <div className="flex-1 flex items-center justify-center p-6"><Spinner size="md" /></div>;

const VocabFlashcards = dynamic(() => import("./VocabFlashcards").then((m) => ({ default: m.VocabFlashcards })), { loading: loader, ssr: false });
const LueckentextView = dynamic(() => import("./LueckentextView").then((m) => ({ default: m.LueckentextView })), { loading: loader, ssr: false });
const VokabeltestView = dynamic(() => import("./VokabeltestView").then((m) => ({ default: m.VokabeltestView })), { loading: loader, ssr: false });
const LernkartenLearnView = dynamic(() => import("./LernkartenLearnView").then((m) => ({ default: m.LernkartenLearnView })), { loading: loader, ssr: false });
const MCExerciseView = dynamic(() => import("./MCExerciseView").then((m) => ({ default: m.MCExerciseView })), { loading: loader, ssr: false });

import type {
  ClozeExercise,
  ExerciseSet,
  GlossaryEntry,
  Source,
  SprachtrainingView,
  StudentStats,
  VocabTestQuestion,
} from "../../_types";

interface SprachtrainingContentProps {
  sprachView: SprachtrainingView;
  setSprachView: (v: SprachtrainingView) => void;
  // Content
  glossary: GlossaryEntry[];
  clozeExercises: ClozeExercise[];
  clozeLoading: boolean;
  vocabQuestions: VocabTestQuestion[];
  vocabLoading: boolean;
  generateCloze: () => void;
  generateVocabTest: () => void;
  // Exercise sets
  exerciseSets: ExerciseSet[];
  activeSet: ExerciseSet | null;
  setActiveSet: (s: ExerciseSet | null) => void;
  loadExerciseSet: (id: number) => Promise<void>;
  loadExerciseSets: (tool?: string) => void;
  deleteExerciseSet: (id: number, tool: string) => void;
  downloadExerciseSet: (s: ExerciseSet) => void;
  setCreateSetTool: (t: string) => void;
  setShowCreateModal: (v: boolean) => void;
  submitSingleAnswer: (setId: number, itemId: number, correct: boolean, newRun?: boolean) => void;
  // Context
  selectedSourceIds: string[];
  pageStats: StudentStats | null;
  isAdmin: boolean;
  sources: Source[];
  refreshProgress: () => void;
  handleAskChat: (text: string) => void;
  handlePillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
}

const TITLE_PREFIX_RE = /^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i;

export function SprachtrainingContent(props: SprachtrainingContentProps) {
  const {
    sprachView, setSprachView,
    glossary, clozeExercises, clozeLoading, vocabQuestions, vocabLoading,
    generateCloze, generateVocabTest,
    exerciseSets, activeSet, setActiveSet,
    loadExerciseSet, loadExerciseSets, deleteExerciseSet, downloadExerciseSet,
    setCreateSetTool, setShowCreateModal, submitSingleAnswer,
    selectedSourceIds, pageStats, isAdmin, sources,
    refreshProgress, handleAskChat, handlePillClick,
  } = props;

  const onSourceClick = (filename: string, page: number, startTime?: number, highlightText?: string) => {
    const src = sources.find((s) => s.filename === filename);
    if (src) handlePillClick(src.uuid, page, filename, highlightText, startTime);
  };

  const toOverviewCrumb = { label: "Studio", onClick: () => setSprachView("overview") };
  const toOverviewWithReset = { label: "Studio", onClick: () => { setActiveSet(null); setSprachView("overview"); } };

  const inner = (() => {
    switch (sprachView) {
      case "karteikarten":
        return (
          <VocabFlashcards
            entries={glossary}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[toOverviewCrumb]}
          />
        );
      case "lueckentext":
        return (
          <LueckentextView
            exercises={clozeExercises}
            loading={clozeLoading}
            onGenerate={generateCloze}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[toOverviewCrumb]}
          />
        );
      case "vokabeltest":
        return (
          <VokabeltestView
            questions={vocabQuestions}
            loading={vocabLoading}
            onGenerate={generateVocabTest}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[toOverviewCrumb]}
          />
        );
      // ─── Lernkarten Sets Flow ──────────────────────────────
      case "lk-sets":
        return (
          <ExerciseSetsOverview
            title="Lernkarten"
            sets={exerciseSets.filter((s) => s.tool === "lernkarten")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("lk-learn")); }}
            onCreate={() => { setCreateSetTool("lernkarten"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "lernkarten")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[toOverviewCrumb]}
            category="sprachtraining"
          />
        );
      case "lk-learn":
        return activeSet ? (
          <LernkartenLearnView
            exerciseSet={activeSet}
            onBack={() => { setSprachView("lk-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={handleAskChat}
            onSourceClick={onSourceClick}
            breadcrumbs={[toOverviewWithReset, { label: "Lernkarten", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
            showTranslation
          />
        ) : null;
      case "lk-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(TITLE_PREFIX_RE, "")}
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("lk-learn")}
            onBack={() => { setSprachView("lk-sets"); setActiveSet(null); loadExerciseSets("lernkarten"); }}
            breadcrumbs={[toOverviewWithReset, { label: "Lernkarten", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
          />
        ) : null;
      // ─── Lückentext Sets Flow ──────────────────────────────
      case "cl-sets":
        return (
          <ExerciseSetsOverview
            title="Lückentext"
            sets={exerciseSets.filter((s) => s.tool === "lueckentext")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("cl-learn")); }}
            onCreate={() => { setCreateSetTool("lueckentext"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "lueckentext")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[toOverviewCrumb]}
            category="sprachtraining"
          />
        );
      case "cl-learn":
        return activeSet ? (
          <MCExerciseView
            exerciseSet={activeSet}
            tool="lueckentext"
            onBack={() => { setSprachView("cl-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={handleAskChat}
            onSourceClick={onSourceClick}
            breadcrumbs={[toOverviewWithReset, { label: "Lückentext", onClick: () => { setActiveSet(null); setSprachView("cl-sets"); } }]}
          />
        ) : null;
      case "cl-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(TITLE_PREFIX_RE, "")}
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("cl-learn")}
            onBack={() => { setSprachView("cl-sets"); setActiveSet(null); loadExerciseSets("lueckentext"); }}
            breadcrumbs={[toOverviewWithReset, { label: "Lückentext", onClick: () => { setActiveSet(null); setSprachView("cl-sets"); } }]}
          />
        ) : null;
      // ─── Vokabeltest Sets Flow ─────────────────────────────
      case "vt-sets":
        return (
          <ExerciseSetsOverview
            title="Begriffe-Quiz"
            sets={exerciseSets.filter((s) => s.tool === "vokabeltest")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("vt-learn")); }}
            onCreate={() => { setCreateSetTool("vokabeltest"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "vokabeltest")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[toOverviewCrumb]}
            category="sprachtraining"
          />
        );
      case "vt-learn":
        return activeSet ? (
          <MCExerciseView
            exerciseSet={activeSet}
            tool="vokabeltest"
            onBack={() => { setSprachView("vt-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={handleAskChat}
            onSourceClick={onSourceClick}
            breadcrumbs={[toOverviewWithReset, { label: "Begriffe-Quiz", onClick: () => { setActiveSet(null); setSprachView("vt-sets"); } }]}
          />
        ) : null;
      case "vt-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(TITLE_PREFIX_RE, "")}
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("vt-learn")}
            onBack={() => { setSprachView("vt-sets"); setActiveSet(null); loadExerciseSets("vokabeltest"); }}
            breadcrumbs={[toOverviewWithReset, { label: "Begriffe-Quiz", onClick: () => { setActiveSet(null); setSprachView("vt-sets"); } }]}
          />
        ) : null;
      default:
        return null;
    }
  })();

  return (
    <div
      style={{ "--accent": "#9333EA", "--accent-rgb": "147,51,234" } as React.CSSProperties}
      className="flex flex-col flex-1 overflow-hidden"
    >
      {inner}
    </div>
  );
}
