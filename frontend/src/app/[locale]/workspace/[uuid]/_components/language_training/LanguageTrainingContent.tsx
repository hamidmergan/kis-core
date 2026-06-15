"use client";

import React from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { ExerciseSetsOverview } from "./ExerciseSetsOverview";
import { ExerciseCompletion } from "./ExerciseCompletion";

const loader = () => <div className="flex-1 flex items-center justify-center p-6"><Spinner size="md" /></div>;

const VocabFlashcards = dynamic(() => import("./VocabFlashcards").then((m) => ({ default: m.VocabFlashcards })), { loading: loader, ssr: false });
const LueckentextView = dynamic(() => import("./LueckentextView").then((m) => ({ default: m.LueckentextView })), { loading: loader, ssr: false });
const VokabeltestView = dynamic(() => import("./VokabeltestView").then((m) => ({ default: m.VokabeltestView })), { loading: loader, ssr: false });
const FlashcardsLearnView = dynamic(() => import("./FlashcardsLearnView").then((m) => ({ default: m.FlashcardsLearnView })), { loading: loader, ssr: false });
const MCExerciseView = dynamic(() => import("./MCExerciseView").then((m) => ({ default: m.MCExerciseView })), { loading: loader, ssr: false });

import type {
  ClozeExercise,
  ExerciseSet,
  GlossaryEntry,
  Source,
  LanguageTrainingView,
  StudentStats,
  VocabTestQuestion,
} from "../../_types";

interface LanguageTrainingContentProps {
  langTrainingView: LanguageTrainingView;
  setSprachView: (v: LanguageTrainingView) => void;
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
  chatLang: "de" | "en";
}

const TITLE_PREFIX_RE = /^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i;

export function LanguageTrainingContent(props: LanguageTrainingContentProps) {
  const {
    langTrainingView, setSprachView,
    glossary, clozeExercises, clozeLoading, vocabQuestions, vocabLoading,
    generateCloze, generateVocabTest,
    exerciseSets, activeSet, setActiveSet,
    loadExerciseSet, loadExerciseSets, deleteExerciseSet, downloadExerciseSet,
    setCreateSetTool, setShowCreateModal, submitSingleAnswer,
    selectedSourceIds, pageStats, isAdmin, sources,
    refreshProgress, handleAskChat, handlePillClick, chatLang,
  } = props;
  const t = useTranslations("workspace.detail.languageTraining");

  const onSourceClick = (filename: string, page: number, startTime?: number) => {
    // Tool chips are nav-only, exactly like chat citations: jump to the page/timestamp,
    // never highlight. (Highlight stays only for the user's own text selection.)
    const src = sources.find((s) => s.filename === filename);
    if (src) handlePillClick(src.uuid, page, filename, undefined, startTime, false);
  };

  const studioLabel = t("common.studio");
  const lernkartenLabel = t("tools.flashcards");
  const lueckentextLabel = t("tools.lueckentext");
  const begriffeQuizLabel = t("tools.vokabeltest");

  const toOverviewCrumb = { label: studioLabel, onClick: () => setSprachView("overview") };
  const toOverviewWithReset = { label: studioLabel, onClick: () => { setActiveSet(null); setSprachView("overview"); } };

  const inner = (() => {
    switch (langTrainingView) {
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
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
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
          />
        ) : null;
      case "lk-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(TITLE_PREFIX_RE, "")}
            toolKey="Flashcards"
            category="language_training"
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("lk-learn")}
            onBack={() => { setSprachView("lk-sets"); setActiveSet(null); loadExerciseSets("flashcards"); }}
            breadcrumbs={[toOverviewWithReset, { label: lernkartenLabel, toolKey: "Flashcards", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
          />
        ) : null;
      // ─── Lückentext Sets Flow ──────────────────────────────
      case "cl-sets":
        return (
          <ExerciseSetsOverview
            title={lueckentextLabel}
            toolKey="Cloze"
            sets={exerciseSets.filter((s) => s.tool === "lueckentext")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("cl-learn")); }}
            onCreate={() => { setCreateSetTool("lueckentext"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "lueckentext")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[toOverviewCrumb]}
            category="language_training"
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
            breadcrumbs={[toOverviewWithReset, { label: lueckentextLabel, toolKey: "Cloze", onClick: () => { setActiveSet(null); setSprachView("cl-sets"); } }]}
            chatLang={chatLang}
          />
        ) : null;
      case "cl-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(TITLE_PREFIX_RE, "")}
            toolKey="Cloze"
            category="language_training"
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("cl-learn")}
            onBack={() => { setSprachView("cl-sets"); setActiveSet(null); loadExerciseSets("lueckentext"); }}
            breadcrumbs={[toOverviewWithReset, { label: lueckentextLabel, toolKey: "Cloze", onClick: () => { setActiveSet(null); setSprachView("cl-sets"); } }]}
          />
        ) : null;
      // ─── Vokabeltest Sets Flow ─────────────────────────────
      case "vt-sets":
        return (
          <ExerciseSetsOverview
            title={begriffeQuizLabel}
            toolKey="TermQuiz"
            sets={exerciseSets.filter((s) => s.tool === "vokabeltest")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("vt-learn")); }}
            onCreate={() => { setCreateSetTool("vokabeltest"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "vokabeltest")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[toOverviewCrumb]}
            category="language_training"
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
            breadcrumbs={[toOverviewWithReset, { label: begriffeQuizLabel, toolKey: "TermQuiz", onClick: () => { setActiveSet(null); setSprachView("vt-sets"); } }]}
            chatLang={chatLang}
          />
        ) : null;
      case "vt-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(TITLE_PREFIX_RE, "")}
            toolKey="TermQuiz"
            category="language_training"
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("vt-learn")}
            onBack={() => { setSprachView("vt-sets"); setActiveSet(null); loadExerciseSets("vokabeltest"); }}
            breadcrumbs={[toOverviewWithReset, { label: begriffeQuizLabel, toolKey: "TermQuiz", onClick: () => { setActiveSet(null); setSprachView("vt-sets"); } }]}
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
