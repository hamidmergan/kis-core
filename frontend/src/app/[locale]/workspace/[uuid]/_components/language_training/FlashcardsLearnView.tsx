import { useEffect, useRef, useState } from "react";
import { Check, XIcon } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { useVoicePlayer } from "@/hooks/useVoicePlayer";
import type { ExerciseItem, ExerciseSet } from "../../_types";
import type { BreadcrumbItem } from "../layout/SubviewHeader";
import { ExerciseHeader } from "./ExerciseHeader";
import { ExerciseNav } from "./ExerciseNav";
import { FlashcardsResults, PendingPrompt } from "./FlashcardsSummary";
import { FlipCard } from "./FlipCard";
import { HintCard } from "./HintCard";
import { SetSourceLegend, sourceNumbers } from "./SetSourceLegend";
import { VocabCard } from "./VocabCard";
import { chatPrompts } from "./_chatPrompts";
import { shuffled } from "./_shuffle";

export function FlashcardsLearnView({
  exerciseSet, onBack, onAnswer, onAskChat, onSourceClick, breadcrumbs, showTranslation, workspaceUuid,
}: {
  exerciseSet: ExerciseSet;
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean, newRun: boolean) => void;
  onAskChat?: (text: string) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number, claim?: string) => void;
  breadcrumbs?: BreadcrumbItem[];
  showTranslation?: boolean;
  /** For the pronunciation route, the set only carries the internal id. */
  workspaceUuid: string;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  // The chat instructions follow the interface language.
  const locale = useLocale();
  const { tip: promptTip, termDeep: promptTermDeep, topicDeep: promptTopicDeep } = chatPrompts(locale);
  const [items, setItems] = useState<ExerciseItem[]>([]);
  const shuffledRef = useRef(false);
  useEffect(() => {
    const raw = exerciseSet.items || [];
    if (raw.length > 0 && !shuffledRef.current) {
      // Vocabulary keeps its order, cards are mixed once.
      setItems(exerciseSet.tool === "flashcards" ? raw : shuffled(raw));
      shuffledRef.current = true;
    }
  }, [exerciseSet.items, exerciseSet.tool]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [results, setResults] = useState<Record<number, boolean>>({});
  const [showResults, setShowResults] = useState(false);
  const [showPendingPrompt, setShowPendingPrompt] = useState(false);
  // One mount of the view is one round, the first answer opens it.
  const runGemeldetRef = useRef(false);
  // The same list available at once, otherwise paging reads the old state.
  const answeredRef = useRef<Set<number>>(new Set());
  // The hint sits ready on the card, the button only expands it.
  const [showHint, setShowHint] = useState(false);
  // The audio stays on the card while the view lives.
  const { playingId, loadingId, failedId, playFromApi } = useVoicePlayer({ keepCache: true });

  const total = items.length;
  const card = items[index];
  const isVocab = exerciseSet.tool === "flashcards";
  // Already graded? Then the two verdict buttons are locked.
  const rated = Boolean(card && card.id in results);
  // The numbering belongs to the set so it matches the legend.
  const srcNumbers = sourceNumbers(exerciseSet.sources);

  // An already rated card opens on the answer side: paging back is for seeing and changing the rating, not guessing again.
  useEffect(() => {
    const offen = items[index];
    setFlipped(Boolean(!isVocab && offen && answeredRef.current.has(offen.id)));
    setShowHint(false);
  }, [index, items, isVocab]);

  function answer(correct: boolean) {
    // The same rating again is nothing new, a different one replaces the old.
    if (!card || results[card.id] === correct) return;
    answeredRef.current.add(card.id);
    setResults((r) => ({ ...r, [card.id]: correct }));
    const neuerDurchgang = !runGemeldetRef.current;
    runGemeldetRef.current = true;
    onAnswer(card.id, correct, neuerDurchgang);
  }

  const pendingItems = () => items.filter((it) => !answeredRef.current.has(it.id));

  function advance() {
    // Which side is up is decided by the effect on the index.
    if (index < total - 1) {
      setIndex(index + 1);
      return;
    }
    if (pendingItems().length > 0) setShowPendingPrompt(true);
    else setShowResults(true);
  }

  function goToFirstPending() {
    const firstPendingIdx = items.findIndex(it => !answeredRef.current.has(it.id));
    if (firstPendingIdx >= 0) setIndex(firstPendingIdx);
    setShowPendingPrompt(false);
  }

  function restart() {
    setShowResults(false);
    setIndex(0);
    setFlipped(false);
    setResults({});
    answeredRef.current = new Set();
    setShowPendingPrompt(false);
    shuffledRef.current = false;
  }

  if (!card && !showResults) return (
    <div className="flex flex-col h-full items-center justify-center gap-3">
      <Spinner size="lg" />
      <p className="text-xs" >{t("common.loading")}</p>
    </div>
  );
  const progressPct = showResults ? 100 : ((index + 1) / total) * 100;
  const legend = (className: string) => (
    <SetSourceLegend
      sources={exerciseSet.sources}
      items={exerciseSet.items}
      onSourceClick={(f) => onSourceClick?.(f, 1)}
      className={className}
    />
  );

  return (
    <div className="flex flex-col h-full">
      <ExerciseHeader title={exerciseSet.title} breadcrumbs={breadcrumbs}
        badgeCategory={isVocab ? "language_training" : "learning_tools"} onBack={onBack} />
      {/* Progress bar as top border */}
      <div className="w-full" style={{ height: 3, backgroundColor: "var(--border)" }}>
        <div className="h-full transition-all duration-500 rounded-r-full" style={{ width: `${progressPct}%`, backgroundColor: "var(--kb)" }} />
      </div>
      {showResults ? (
        <FlashcardsResults isVocab={isVocab} total={total} results={results} onAgain={restart} onDone={onBack} />
      ) : showPendingPrompt ? (
        // The same counting as when the follow-up is triggered.
        <PendingPrompt pendingCount={pendingItems().length} onViewPending={goToFirstPending}
          onFinish={() => { setShowPendingPrompt(false); setShowResults(true); }} />
      ) : card && isVocab ? (
        // ── Vocabulary: single-page card, no flip ──
        <div className="flex-1 overflow-y-auto px-3 sm:px-4 pt-4 sm:pt-6 pb-3">
          <div className="mx-auto w-full flex flex-col gap-3" style={{ maxWidth: 560 }}>
            <VocabCard
              card={card}
              showTranslation={showTranslation}
              numbers={srcNumbers}
              onSourceClick={onSourceClick}
              onLearnMore={onAskChat ? () => onAskChat(promptTermDeep(card.front)) : undefined}
              speech={{
                playingId, loadingId, failedId,
                play: exerciseSet.speech_enabled
                  ? (itemId) => void playFromApi(
                    String(itemId),
                    `/api/ai-assistant/workspaces/${workspaceUuid}/exercise-sets/${exerciseSet.id}/items/${itemId}/speak`,
                  )
                  : undefined,
              }}
            />
            {/* Back and next. A vocabulary term is not rated, it counts as seen once left; paging back does not change that. */}
            <ExerciseNav index={index} total={total}
              onPrev={() => setIndex(index - 1)} onNext={() => { answer(true); advance(); }}
              backLabel={t("common.back")} nextLabel={t("flashcardsLearn.nextTerm")}
              finishLabel={t("common.finish")} />

            {legend("pt-1")}
          </div>
        </div>
      ) : card ? (
        // ── Flashcards: flip card ──
        // Scroll outside, centre inside: the block grows with long content instead of being cut off at the top.
        <div className="flex-1 overflow-y-auto flex flex-col items-center px-3 sm:px-4 pt-4 sm:pt-6 pb-3">
          <div className="flex-1 w-full flex flex-col items-center justify-center gap-3" style={{ maxWidth: 560 }}>
            <FlipCard
              card={card}
              flipped={flipped}
              showHint={showHint}
              numbers={srcNumbers}
              onSourceClick={onSourceClick}
              // Older cards without a delivered hint take the old path through the chat.
              onHint={card.extras?.tip
                ? () => setShowHint((v) => !v)
                : onAskChat ? () => onAskChat(promptTip(card.front)) : undefined}
              onLearnMore={onAskChat ? () => onAskChat(promptTopicDeep(card.front)) : undefined}
            />
            {/* The hint sits BELOW the card, not on it: it belongs to the question, not the back, and is gone once flipped. */}
            {showHint && !flipped && card.extras?.tip && (
              <div className="w-full" style={{ maxWidth: 560 }}>
                <HintCard text={card.extras.tip} />
              </div>
            )}
            {/* Rating. Labelled instead of two bare circles and always clickable so paging back can change it; the chosen one is filled, the other recedes. */}
            <div className="w-full flex flex-wrap items-center justify-center gap-3 min-h-12">
              {flipped ? (
                <div className="w-full flex items-center gap-2.5">
                  <button key="again" type="button" onClick={() => answer(false)}
                    aria-pressed={rated && results[card.id] === false}
                    className={`btn-outline-danger flex-1 min-w-0 px-3 py-2.5 rounded-full text-xs font-semibold flex items-center justify-center gap-1.5 transition-all${results[card.id] === false ? " is-picked" : ""}${results[card.id] === true ? " opacity-50" : ""}`}>
                    <XIcon size={14} weight="bold" className="shrink-0" />
                    <span className="truncate">{t("common.notKnew")}</span>
                  </button>
                  <button key="knew" type="button" onClick={() => answer(true)}
                    aria-pressed={rated && results[card.id] === true}
                    className={`btn-outline-success flex-1 min-w-0 px-3 py-2.5 rounded-full text-xs font-semibold flex items-center justify-center gap-1.5 transition-all${results[card.id] === true ? " is-picked" : ""}${results[card.id] === false ? " opacity-50" : ""}`}>
                    <Check size={14} weight="bold" className="shrink-0" />
                    <span className="truncate">{t("common.knew")}</span>
                  </button>
                </div>
              ) : (
                <button key="show-answer" type="button" onClick={() => setFlipped(true)}
                  className="btn-ghost px-4 py-1.5 rounded-full text-xs font-semibold text-kb-dark transition-colors">
                  {t("common.showAnswer")}
                </button>
              )}
            </div>
            {/* Flip belongs to the card and sits above paging but not in the button row: it is no rating. Same style as "show answer", btn-ghost brings the 2px ring. */}
            {/* No placeholder on the front: the empty line stood out more than the slight shift its absence costs on flip. */}
            {flipped && (
              <button type="button" onClick={() => setFlipped(false)}
                className="btn-ghost px-4 py-1.5 rounded-full text-xs font-semibold text-kb-dark transition-colors">
                {t("common.showQuestion")}
              </button>
            )}
            {/* Back and next are always there; skip a card now and return later. */}
            <ExerciseNav index={index} total={total}
              onPrev={() => setIndex(index - 1)} onNext={advance}
              backLabel={t("common.back")} nextLabel={t("common.next")} finishLabel={t("common.finish")} />
          </div>

          {/* Follows the growing block and therefore always lands at the bottom. */}
          {legend("w-full shrink-0 pt-5")}
        </div>
      ) : null}
    </div>
  );
}
