"use client";

import React from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { ExerciseSetsOverview } from "./ExerciseSetsOverview";
import { ExerciseCompletion } from "./ExerciseCompletion";
import { setDisplayTitle } from "./_setTitle";

const loader = () => <div className="flex-1 flex items-center justify-center p-6"><Spinner size="md" /></div>;

const GrammarExerciseView = dynamic(() => import("./GrammarExerciseView").then((m) => ({ default: m.GrammarExerciseView })), { loading: loader, ssr: false });
const FlashcardsLearnView = dynamic(() => import("./FlashcardsLearnView").then((m) => ({ default: m.FlashcardsLearnView })), { loading: loader, ssr: false });
const ClozeExerciseView = dynamic(() => import("./ClozeExerciseView").then((m) => ({ default: m.ClozeExerciseView })), { loading: loader, ssr: false });

import type {
  ExerciseSet,
  Source,
  LanguageTrainingView,
} from "../../_types";

interface LanguageTrainingContentProps {
  langTrainingView: LanguageTrainingView;
  setSprachView: (v: LanguageTrainingView) => void;
  // Exercise sets
  exerciseSets: ExerciseSet[];
  activeSet: ExerciseSet | null;
  setActiveSet: (s: ExerciseSet | null) => void;
  loadExerciseSet: (id: number) => Promise<void>;
  loadExerciseSets: (tool?: string) => void;
  deleteExerciseSet: (id: number, tool: string) => void;
  renameExerciseSet: (id: number, tool: string, title: string) => Promise<void>;
  retryExerciseSet: (id: number, tool: string) => void;
  downloadExerciseSet: (s: ExerciseSet) => void;
  setCreateSetTool: (t: string) => void;
  setShowCreateModal: (v: boolean) => void;
  submitSingleAnswer: (setId: number, itemId: number, correct: boolean, newRun: boolean) => void;
  // Context
  selectedSourceIds: string[];
  workspaceUuid: string;
  isAdmin: boolean;
  sources: Source[];
  refreshProgress: () => void;
  handleAskChat: (text: string) => void;
  handlePillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean, hideTranscript?: boolean) => void;
  /** No longer read here, the page still passes it. */
  chatLang?: "de" | "en";
}

export function LanguageTrainingContent(props: LanguageTrainingContentProps) {
  const {
    langTrainingView, setSprachView,
    exerciseSets, activeSet, setActiveSet,
    loadExerciseSet, loadExerciseSets, deleteExerciseSet, renameExerciseSet, retryExerciseSet, downloadExerciseSet,
    setCreateSetTool, setShowCreateModal, submitSingleAnswer,
    selectedSourceIds, workspaceUuid, isAdmin, sources,
    refreshProgress, handleAskChat, handlePillClick,
  } = props;
  const t = useTranslations("workspace.detail.languageTraining");
  // Grammar reports its score, the summary page shows real numbers.
  const [grammarScore, setGrammarScore] = React.useState<{ correct: number; total: number } | null>(null);
  // The cloze reports the same way, its gaps count individually.
  const [clozeScore, setClozeScore] = React.useState<{ correct: number; total: number } | null>(null);

  const onSourceClick = (filename: string, page: number, startTime?: number) => {
    // Tool chips only jump, only a selection of your own is highlighted.
    const src = sources.find((s) => s.filename === filename);
    if (src) handlePillClick(src.uuid, page, filename, undefined, startTime, false);
  };

  const studioLabel = t("common.studio");
  const lernkartenLabel = t("tools.flashcards");
  const grammarLabel = t("tools.grammar");
  const vocabularyLabel = t("tools.vocabulary");

  const toOverviewCrumb = { label: studioLabel, onClick: () => setSprachView("overview") };
  const toOverviewWithReset = { label: studioLabel, onClick: () => { setActiveSet(null); setSprachView("overview"); } };

  // The three trainers share the list of their sets, only tool, colour key and target view differ.
  const setsOverview = (tool: string, toolKey: string, title: string, learnView: LanguageTrainingView) => (
    <ExerciseSetsOverview
      title={title}
      toolKey={toolKey}
      sets={exerciseSets.filter((s) => s.tool === tool)}
      onBack={() => setSprachView("overview")}
      onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView(learnView)); }}
      onCreate={() => { setCreateSetTool(tool); setShowCreateModal(true); }}
      onDelete={(id) => deleteExerciseSet(id, tool)}
      onRename={(id, newTitle) => renameExerciseSet(id, tool, newTitle)}
      onRetry={(id) => retryExerciseSet(id, tool)}
      onDownload={isAdmin ? downloadExerciseSet : undefined}
      sourceCount={selectedSourceIds.length}
      breadcrumbs={[toOverviewCrumb]}
      category="language_training"
    />
  );
  // The path inside a set: studio, then the tool leading back to its list.
  const setCrumbs = (label: string, toolKey: string, setsView: LanguageTrainingView) => [
    toOverviewWithReset,
    { label, toolKey, onClick: () => { setActiveSet(null); setSprachView(setsView); } },
  ];
  // The summary page takes a list, so the reported score is spread over it.
  const scoreAsResults = (score: { correct: number; total: number } | null) =>
    Array.from({ length: score?.total ?? 0 }, (_, i) => ({ item_id: i, correct: i < (score?.correct ?? 0) }));

  const inner = (() => {
    switch (langTrainingView) {
      // ─── Flashcards Sets Flow ──────────────────────────────
      case "lk-sets":
        return setsOverview("flashcards", "Flashcards", lernkartenLabel, "lk-learn");
      case "lk-learn":
        return activeSet ? (
          <FlashcardsLearnView
            exerciseSet={activeSet}
            onBack={() => { setSprachView("lk-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={handleAskChat}
            onSourceClick={onSourceClick}
            breadcrumbs={setCrumbs(lernkartenLabel, "Flashcards", "lk-sets")}
            showTranslation
            workspaceUuid={workspaceUuid}
          />
        ) : null;
      // ─── Grammar exercise set flow ─────────────────────────
      case "gr-sets":
        return setsOverview("grammatik", "Grammar", grammarLabel, "gr-learn");
      case "gr-learn":
        // Always the grammar view, it decides per exercise.
        return activeSet ? (
          <GrammarExerciseView
            exerciseSet={activeSet}
            workspaceUuid={workspaceUuid}
            onBack={() => { setSprachView("gr-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onSourceClick={onSourceClick}
            onFinish={(correct, total) => { setGrammarScore({ correct, total }); setSprachView("gr-complete"); }}
            breadcrumbs={setCrumbs(grammarLabel, "Grammar", "gr-sets")}
          />
        ) : null;
      case "gr-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={setDisplayTitle(activeSet.title)}
            toolKey="Grammar"
            category="language_training"
            // Here the real score is known and the summary page shows it.
            results={scoreAsResults(grammarScore)}
            total={grammarScore?.total ?? activeSet.card_count}
            onRetryWrong={() => setSprachView("gr-learn")}
            onBack={() => { setSprachView("gr-sets"); setActiveSet(null); loadExerciseSets("grammatik"); }}
            breadcrumbs={setCrumbs(grammarLabel, "Grammar", "gr-sets")}
          />
        ) : null;
      // ─── Vocabulary cloze ──────────────────────────────────
      case "wo-sets":
        return setsOverview("wortschatz", "Cloze", vocabularyLabel, "wo-learn");
      case "wo-learn":
        return activeSet ? (
          <ClozeExerciseView
            exerciseSet={activeSet}
            onBack={() => { setSprachView("wo-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onSourceClick={onSourceClick}
            onFinish={(correct, total) => { setClozeScore({ correct, total }); setSprachView("wo-complete"); }}
            breadcrumbs={setCrumbs(vocabularyLabel, "Cloze", "wo-sets")}
          />
        ) : null;
      case "wo-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title}
            toolKey="Cloze"
            category="language_training"
            // The gaps are counted, not the single exercise.
            results={scoreAsResults(clozeScore)}
            total={clozeScore?.total ?? 0}
            onRetryWrong={() => setSprachView("wo-learn")}
            onBack={() => { setSprachView("wo-sets"); setActiveSet(null); loadExerciseSets("wortschatz"); }}
            breadcrumbs={setCrumbs(vocabularyLabel, "Cloze", "wo-sets")}
          />
        ) : null;
      default:
        return null;
    }
  })();

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {inner}
    </div>
  );
}
