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
// The grammar quiz ticks its answer, so it runs in the same view the quiz uses.
const MCExerciseView = dynamic(() => import("./MCExerciseView").then((m) => ({ default: m.MCExerciseView })), { loading: loader, ssr: false });

import type {
  ExerciseSet,
  Source,
  LanguageTrainingView,
  StudentStats,
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
  retryExerciseSet: (id: number, tool: string) => void;
  downloadExerciseSet: (s: ExerciseSet) => void;
  setCreateSetTool: (t: string) => void;
  setShowCreateModal: (v: boolean) => void;
  submitSingleAnswer: (setId: number, itemId: number, correct: boolean) => void;
  // Context
  selectedSourceIds: string[];
  workspaceUuid: string;
  pageStats: StudentStats | null;
  isAdmin: boolean;
  sources: Source[];
  refreshProgress: () => void;
  handleAskChat: (text: string) => void;
  handlePillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean, hideTranscript?: boolean) => void;
  chatLang: "de" | "en";
}

const TITLE_PREFIX_RE = /^(Lernkarten|Grammatik-Übung|Quiz|Hörverstehen)\s*(aus|von)\s*/i;

export function LanguageTrainingContent(props: LanguageTrainingContentProps) {
  const {
    langTrainingView, setSprachView,
    exerciseSets, activeSet, setActiveSet,
    loadExerciseSet, loadExerciseSets, deleteExerciseSet, retryExerciseSet, downloadExerciseSet,
    setCreateSetTool, setShowCreateModal, submitSingleAnswer,
    selectedSourceIds, workspaceUuid, pageStats, isAdmin, sources,
    refreshProgress, handleAskChat, handlePillClick, chatLang,
  } = props;
  const t = useTranslations("workspace.detail.languageTraining");
  // The grammar run reports its score when it finishes, so the summary screen can
  // show the real numbers rather than the placeholder the MC flows use.
  const [grammarScore, setGrammarScore] = React.useState<{ correct: number; total: number } | null>(null);

  const onSourceClick = (filename: string, page: number, startTime?: number) => {
    // Tool chips are nav-only, exactly like chat citations: jump to the page/timestamp,
    // never highlight. (Highlight stays only for the user's own text selection.)
    const src = sources.find((s) => s.filename === filename);
    if (src) handlePillClick(src.uuid, page, filename, undefined, startTime, false);
  };

  // Beim Hör- und Leseverstehen wird die Aufnahme OHNE Transkript geöffnet. Sonst
  // steht der Text eben im linken Fenster und die Hörübung prüft wieder Lesen.
  const onListeningSourceClick = (filename: string, page: number, startTime?: number) => {
    const src = sources.find((s) => s.filename === filename);
    if (src) handlePillClick(src.uuid, page, filename, undefined, startTime, false, true);
  };

  const studioLabel = t("common.studio");
  const lernkartenLabel = t("tools.flashcards");
  const grammarLabel = t("tools.grammar");
  const listeningLabel = t("tools.listening");
  // Hör- und Leseverstehen zählt jede ausgewählte Quelle. Die Auswahl entscheidet über
  // die Fertigkeit: nur Aufnahmen heißt Hören, nur Text heißt Lesen, beides heißt beides.
  // Früher zählten hier nur Aufnahmen, weil die Route die PDFs weggefiltert hat.

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
            onRetry={(id) => retryExerciseSet(id, "flashcards")}
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
            onAnswer={(itemId, correct) => submitSingleAnswer(activeSet.id, itemId, correct)}
            onAskChat={handleAskChat}
            onSourceClick={onSourceClick}
            breadcrumbs={[toOverviewWithReset, { label: lernkartenLabel, toolKey: "Flashcards", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
            showTranslation
            chatLang={chatLang}
          />
        ) : null;
      // ─── Grammatik-Übung Sets Flow ─────────────────────────
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
            onRetry={(id) => retryExerciseSet(id, "grammatik")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[toOverviewCrumb]}
            category="language_training"
          />
        );
      case "gr-learn": {
        if (!activeSet) return null;
        // Immer die Grammatik-Ansicht. Sie entscheidet je AUFGABE, ob angekreuzt oder
        // getippt wird.
        //
        // Vorher stand hier eine Weiche über das ganze Set: hatte eine einzige Aufgabe
        // Optionen, ging alles in die Ankreuz-Ansicht. Seit ein Set die vier Formate
        // mischt, traf das immer zu, und die Freitext-Aufgaben erschienen als nackter
        // Satz ohne Eingabefeld. Gemeldet am 2026-08-05.
        const grammarCrumbs = [toOverviewWithReset, { label: grammarLabel, toolKey: "Grammar", onClick: () => { setActiveSet(null); setSprachView("gr-sets"); } }];
        return (
          <GrammarExerciseView
            exerciseSet={activeSet}
            workspaceUuid={workspaceUuid}
            onBack={() => { setSprachView("gr-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct) => submitSingleAnswer(activeSet.id, itemId, correct)}
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
            // Unlike the MC tools the run's real score is known here, so the summary
            // shows it instead of a placeholder zero.
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
      // ─── Hörverstehen Sets Flow ────────────────────────────
      // Angekreuzt wird wie beim Quiz, deshalb dieselbe Ansicht. Der Unterschied
      // steckt in den Aufgaben (Richtig/Falsch kommt dazu) und in den Quellen
      // (nur Ton und Bild), nicht in der Bedienung.
      case "hv-sets":
        return (
          <ExerciseSetsOverview
            title={listeningLabel}
            toolKey="Listening"
            sets={exerciseSets.filter((s) => s.tool === "hoerverstehen")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("hv-learn")); }}
            onCreate={() => { setCreateSetTool("hoerverstehen"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "hoerverstehen")}
            onRetry={(id) => retryExerciseSet(id, "hoerverstehen")}
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[toOverviewCrumb]}
            category="language_training"
          />
        );
      case "hv-learn":
        return activeSet ? (
          <MCExerciseView
            exerciseSet={activeSet}
            onBack={() => { setSprachView("hv-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct) => submitSingleAnswer(activeSet.id, itemId, correct)}
            onAskChat={handleAskChat}
            onSourceClick={onListeningSourceClick}
            breadcrumbs={[toOverviewWithReset, { label: listeningLabel, toolKey: "Listening", onClick: () => { setActiveSet(null); setSprachView("hv-sets"); } }]}
            chatLang={chatLang}
            badgeCategory="language_training"
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
