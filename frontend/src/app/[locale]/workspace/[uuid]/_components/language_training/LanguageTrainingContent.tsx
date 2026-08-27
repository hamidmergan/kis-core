"use client";

import React from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { ExerciseSetsOverview } from "./ExerciseSetsOverview";
import { ExerciseCompletion } from "./ExerciseCompletion";

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
  chatLang: "de" | "en";
}

const TITLE_PREFIX_RE = /^(Lernkarten|Grammatik-Übung|Quiz)\s*(aus|von)\s*/i;

export function LanguageTrainingContent(props: LanguageTrainingContentProps) {
  const {
    langTrainingView, setSprachView,
    exerciseSets, activeSet, setActiveSet,
    loadExerciseSet, loadExerciseSets, deleteExerciseSet, renameExerciseSet, retryExerciseSet, downloadExerciseSet,
    setCreateSetTool, setShowCreateModal, submitSingleAnswer,
    selectedSourceIds, workspaceUuid, isAdmin, sources,
    refreshProgress, handleAskChat, handlePillClick, chatLang,
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

  const inner = (() => {
    switch (langTrainingView) {
      // ─── Flashcards Sets Flow ──────────────────────────────
      case "lk-sets":
        return (
          <ExerciseSetsOverview
            title={lernkartenLabel}
            toolKey="Flashcards"
            sets={exerciseSets.filter((s) => s.tool === "flashcards")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("lk-learn")); }}
            onCreate={() => { setCreateSetTool("flashcards"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "flashcards")}
            onRename={(id, title) => renameExerciseSet(id, "flashcards", title)}
            onRetry={(id) => retryExerciseSet(id, "flashcards")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            breadcrumbs={[toOverviewCrumb]}
            category="language_training"
          />
        );
      case "lk-learn":
        return activeSet ? (
          <FlashcardsLearnView
            exerciseSet={activeSet}
            onBack={() => { setSprachView("lk-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={handleAskChat}
            onSourceClick={onSourceClick}
            breadcrumbs={[toOverviewWithReset, { label: lernkartenLabel, toolKey: "Flashcards", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
            showTranslation
            chatLang={chatLang}
            workspaceUuid={workspaceUuid}
          />
        ) : null;
      // ─── Grammar exercise set flow ─────────────────────────
      case "gr-sets":
        return (
          <ExerciseSetsOverview
            title={grammarLabel}
            toolKey="Grammar"
            sets={exerciseSets.filter((s) => s.tool === "grammatik")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("gr-learn")); }}
            onCreate={() => { setCreateSetTool("grammatik"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "grammatik")}
            onRename={(id, title) => renameExerciseSet(id, "grammatik", title)}
            onRetry={(id) => retryExerciseSet(id, "grammatik")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            breadcrumbs={[toOverviewCrumb]}
            category="language_training"
          />
        );
      case "gr-learn": {
        if (!activeSet) return null;
        // Always the grammar view, it decides per exercise.
        const grammarCrumbs = [toOverviewWithReset, { label: grammarLabel, toolKey: "Grammar", onClick: () => { setActiveSet(null); setSprachView("gr-sets"); } }];
        return (
          <GrammarExerciseView
            exerciseSet={activeSet}
            workspaceUuid={workspaceUuid}
            onBack={() => { setSprachView("gr-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onSourceClick={onSourceClick}
            onFinish={(correct, total) => { setGrammarScore({ correct, total }); setSprachView("gr-complete"); }}
            breadcrumbs={grammarCrumbs}
          />
        );
      }
      case "gr-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(TITLE_PREFIX_RE, "")}
            toolKey="Grammar"
            category="language_training"
            // Here the real score is known and the summary page shows it.
            results={Array.from({ length: grammarScore?.total ?? 0 }, (_, i) => ({
              item_id: i,
              correct: i < (grammarScore?.correct ?? 0),
            }))}
            total={grammarScore?.total ?? activeSet.card_count}
            onRetryWrong={() => setSprachView("gr-learn")}
            onBack={() => { setSprachView("gr-sets"); setActiveSet(null); loadExerciseSets("grammatik"); }}
            breadcrumbs={[toOverviewWithReset, { label: grammarLabel, toolKey: "Grammar", onClick: () => { setActiveSet(null); setSprachView("gr-sets"); } }]}
          />
        ) : null;
      // ─── Vocabulary cloze ──────────────────────────────────
      case "wo-sets":
        return (
          <ExerciseSetsOverview
            title={vocabularyLabel}
            toolKey="Cloze"
            sets={exerciseSets.filter((s) => s.tool === "wortschatz")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("wo-learn")); }}
            onCreate={() => { setCreateSetTool("wortschatz"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "wortschatz")}
            onRename={(id, title) => renameExerciseSet(id, "wortschatz", title)}
            onRetry={(id) => retryExerciseSet(id, "wortschatz")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            breadcrumbs={[toOverviewCrumb]}
            category="language_training"
          />
        );
      case "wo-learn": {
        if (!activeSet) return null;
        const clozeCrumbs = [toOverviewWithReset, { label: vocabularyLabel, toolKey: "Cloze", onClick: () => { setActiveSet(null); setSprachView("wo-sets"); } }];
        return (
          <ClozeExerciseView
            exerciseSet={activeSet}
            onBack={() => { setSprachView("wo-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onSourceClick={onSourceClick}
            onFinish={(correct, total) => { setClozeScore({ correct, total }); setSprachView("wo-complete"); }}
            breadcrumbs={clozeCrumbs}
          />
        );
      }
      case "wo-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title}
            toolKey="Cloze"
            category="language_training"
            // The gaps are counted, not the single exercise.
            results={Array.from({ length: clozeScore?.total ?? 0 }, (_, i) => ({
              item_id: i,
              correct: i < (clozeScore?.correct ?? 0),
            }))}
            total={clozeScore?.total ?? 0}
            onRetryWrong={() => setSprachView("wo-learn")}
            onBack={() => { setSprachView("wo-sets"); setActiveSet(null); loadExerciseSets("wortschatz"); }}
            breadcrumbs={[toOverviewWithReset, { label: vocabularyLabel, toolKey: "Cloze", onClick: () => { setActiveSet(null); setSprachView("wo-sets"); } }]}
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
