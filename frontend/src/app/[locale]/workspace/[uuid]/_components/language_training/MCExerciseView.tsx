import React, { useContext, useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight, Chat, Check, Lightbulb, SidebarSimple } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import HelpTooltip from "@/components/ui/HelpTooltip";
import type { ExerciseItem, ExerciseItemSource, ExerciseSet } from "../../_types";
import { _chunkLabel, _getChipIcon, _md, _sourceChipKey } from "../../_utils";
import { MinimizeContext } from "../../_context";
import { _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";
import { ExerciseNav } from "./ExerciseNav";
import { HintCard } from "./HintCard";
import { SetSourceLegend, sourceNumbers, sourceTag } from "./SetSourceLegend";
import { shuffleOptions } from "./_shuffle";

export function MCExerciseView({
  exerciseSet, onBack, onAnswer, onAskChat, onSourceClick, breadcrumbs, chatLang = "de",
  badgeCategory = "learning_tools", showChatHelp = true,
}: {
  exerciseSet: ExerciseSet;
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean, newRun: boolean) => void;
  onAskChat: (text: string) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number, claim?: string) => void;
  breadcrumbs?: BreadcrumbItem[];
  chatLang?: "de" | "en";
  // The view also serves the grammar quiz with its own colour.
  badgeCategory?: "learning_tools" | "language_training";
  // Grammar leaves the chat buttons out, they lead away from the exercise.
  showChatHelp?: boolean;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const tChip = useTranslations("sourceChip");
  // The chat instructions follow the interface language.
  void chatLang;
  const locale = useLocale();
  const promptTip = (term: string) => locale === "en"
    ? `Give me a brief hint for the following question, WITHOUT revealing the answer: "${term}"`
    : `Gib mir einen kurzen Tipp zur folgenden Frage, OHNE die Antwort zu verraten.: „${term}"`;
  const promptTermDeep = (term: string) => locale === "en"
    ? `Explain the term "${term}" in detail. What does it mean, in which contexts is it used, and what are the important relationships?`
    : `Erkläre mir den Begriff „${term}" genauer. Was bedeutet er, in welchem Kontext wird er verwendet und welche Zusammenhänge sind wichtig?`;
  const promptTopicDeep = (term: string) => locale === "en"
    ? `Explain the following topic in more detail: "${term}". What are important details, examples, and connections?`
    : `Erkläre mir folgendes Thema genauer: „${term}". Was sind wichtige Details, Beispiele und Zusammenhänge?`;
  const minimize = useContext(MinimizeContext);
  const [shuffledItems, setShuffledItems] = useState<ExerciseItem[]>([]);
  const shuffledRef = useRef(false);
  useEffect(() => {
    const raw = exerciseSet.items || [];
    if (raw.length > 0 && !shuffledRef.current) {
      const arr = [...raw];
      for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[arr[i], arr[j]] = [arr[j], arr[i]]; }
      const shuffled = arr.map(shuffleOptions);
      setShuffledItems(shuffled);
      shuffledRef.current = true;
    }
  }, [exerciseSet.items]);
  const items = shuffledItems;
  const [index, setIndex] = useState(0);
  // The choice hangs on the exercise, only that way can you go back and forth.
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [results, setResults] = useState<{ item_id: number; correct: boolean }[]>([]);
  const [, setStreak] = useState(0);
  const [showResults, setShowResults] = useState(false);
  // The hint sits ready on the exercise, the loading state belongs to the fallback.
  const [showHint, setShowHint] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  // The hover state lives in state, an inline border beats every class.
  const [hovered, setHovered] = useState<number | null>(null);
  // One mount of the view is one round, a retry resets it.
  const runGemeldetRef = useRef(false);

  const total = items.length;
  const card = items[index];
  // A gap exercise is recognised by its marker, not by a separate tool.
  const isGap = /___+/.test(card?.front || "");
  // The numbering belongs to the set so it matches the legend.
  const srcNumbers = sourceNumbers(exerciseSet.sources);
  const selected = card ? picks[card.id] ?? null : null;
  const answered = selected !== null;
  const isCorrect = answered && selected === card?.correct_idx;

  function select(optIdx: number) {
    if (answered || !card) return;
    setPicks((p) => ({ ...p, [card.id]: optIdx }));
    const correct = optIdx === card.correct_idx;
    setResults(prev => [...prev, { item_id: card.id, correct }]);
    if (correct) setStreak((s) => s + 1);
    else setStreak(0);
    const neuerDurchgang = !runGemeldetRef.current;
    runGemeldetRef.current = true;
    onAnswer(card.id, correct, neuerDurchgang);
  }

  function goTo(next: number) {
    setIndex(next);
    setShowHint(false);
    // The pointer sits on the Weiter button, not on an option of the next card.
    setHovered(null);
  }

  function advance() {
    if (index >= total - 1) setShowResults(true);
    else goTo(index + 1);
  }

  async function requestHint() {
    if (!card || hintLoading) return;
    // Older exercises without a hint take the old path through the chat.
    if (card.extras?.tip) { setShowHint((v) => !v); return; }
    setHintLoading(true);
    try {
      onAskChat(promptTip(card.front));
    } catch { /* ignore */ }
    setHintLoading(false);
  }

  if (!card && !showResults) return (
    <div className="flex flex-col h-full items-center justify-center gap-3">
      <Spinner size="lg" />
      <p className="text-xs" >{t("common.loading")}</p>
    </div>
  );
  const progressPct = showResults ? 100 : ((index + 1) / total) * 100;
  const options = card?.options || [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div data-panel-header="" className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
        <button type="button" onClick={onBack}
          className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          style={{ backgroundColor: "var(--surface-dim)" }}>
          <CaretLeft size={13} />
        </button>
        {breadcrumbs && breadcrumbs.length > 0 ? (<div className="flex items-center gap-1 text-xs min-w-0 flex-1">{breadcrumbs.map((b, i) => { const bBadge = _getToolBadge(b.toolKey, badgeCategory); return (<React.Fragment key={i}>{bBadge ? (<button type="button" onClick={b.onClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={{ color: bBadge.color }}>{b.label}</button>) : (<button type="button" onClick={b.onClick} className="font-medium shrink-0 opacity-60 hover:opacity-100 transition-opacity" style={{ color: "var(--muted)" }}>{b.label}</button>)}<CaretRight size={9} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" /></React.Fragment>); })}<span className="font-semibold truncate" style={{ color: "var(--foreground)" }}>{exerciseSet.title.replace(/^(Lernkarten|Grammatik-Übung|Quiz)\s*(aus|von)\s*/i, "")}</span></div>) : (<span className="text-xs font-semibold flex-1 truncate" style={{ color: "var(--foreground)" }}>{exerciseSet.title.replace(/^(Lernkarten|Grammatik-Übung|Quiz)\s*(aus|von)\s*/i, "")}</span>)}
        {minimize && (
          <button type="button" onClick={minimize}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title={t("common.minimizePanel")}>
            <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
          </button>
        )}
      </div>
      {/* Progress — rendered inside question card */}
      {/* Quiz Results */}
      {showResults ? (
        <div className="flex-1 flex flex-col items-center justify-center px-6 gap-3">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
            style={{ backgroundColor: "#1a8a5c", boxShadow: "0 4px 20px rgba(26,138,92,0.25)" }}>
            <Check size={30} weight="bold" color="white" />
          </div>
          <h3 className="text-lg font-semibold">{t("mcExercise.quizCompleted")}</h3>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            {t.rich("mcExercise.quizScore", {
              correct: results.filter(r => r.correct).length,
              total,
              pct: Math.round((results.filter(r => r.correct).length / total) * 100),
              hl: (chunks) => <strong style={{ color: "#1a8a5c" }}>{chunks}</strong>,
            })}
          </p>
          <div className="flex gap-3 mt-4">
            <button type="button" onClick={() => { setShowResults(false); setIndex(0); setPicks({}); setResults([]); shuffledRef.current = false; runGemeldetRef.current = false; }}
              className="btn-outline-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
              {t("mcExercise.tryAgain")}
            </button>
            <button type="button" onClick={onBack}
              className="btn-fill-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
              {t("common.done")}
            </button>
          </div>
        </div>
      ) : card ? (
        <>
          {/* Progress bar */}
          <div className="w-full" style={{ height: 3, backgroundColor: "var(--border)" }}>
            <div className="h-full transition-all duration-500 rounded-r-full" style={{ width: `${progressPct}%`, backgroundColor: "var(--kb)" }} />
          </div>
          {/* Question Card */}
          {/* Scroll outside, centre inside: the block grows with a long task instead of being cut off at the top. */}
          <div className="flex-1 overflow-y-auto p-4 flex flex-col">
            <div className="flex-1 mx-auto w-full flex flex-col justify-center gap-3" style={{ maxWidth: 560 }}>
              <div className="rounded-2xl flex flex-col gap-4 overflow-hidden" style={{ backgroundColor: "var(--surface)", boxShadow: "0 4px 20px rgba(0,40,60,0.08)" }}>
                <div className="px-6 pt-5 pb-6 flex flex-col gap-4">
                  {/* Question text */}
                  {isGap ? (
                    <p className="text-sm leading-relaxed" style={{ color: "var(--foreground)" }}
                      dangerouslySetInnerHTML={{
                        __html: card.front.replace(
                          /___+/g,
                          answered
                            ? `<span style="font-weight:700;color:${isCorrect ? '#1a8a5c' : '#d4453a'};border-bottom:2px solid ${isCorrect ? '#1a8a5c' : '#d4453a'};padding:0 4px">${card.back}</span>`
                            : '<span style="display:inline-block;min-width:80px;color:var(--kb);font-weight:700;padding:0 4px">__________</span>'
                        ),
                      }}
                    />
                  ) : (
                    // pre-line keeps the blank line between instruction and sentence.
                    <p className="text-sm font-semibold leading-snug" style={{ color: "var(--foreground)", whiteSpace: "pre-line" }} dangerouslySetInnerHTML={{ __html: _md(card.front) }} />
                  )}
                  {/* Options */}
                  <div className="flex flex-col gap-2 mt-1">
                    {options.map((opt, oi) => {
                      const isThis = selected === oi;
                      const isRight = oi === card.correct_idx;
                      let borderColor = "var(--border)";
                      let bg = "var(--background)";
                      let dotBg = "var(--border)";
                      let dotColor = "var(--muted)";
                      if (answered && isRight) { borderColor = "#1a8a5c"; bg = "rgba(26,138,92,0.08)"; dotBg = "#1a8a5c"; dotColor = "#fff"; }
                      else if (answered && isThis && !isRight) { borderColor = "#d4453a"; bg = "rgba(212,69,58,0.07)"; dotBg = "#d4453a"; dotColor = "#fff"; }
                      // Only before answering, afterwards the border carries the result.
                      if (!answered && hovered === oi) { borderColor = "var(--kb)"; }
                      return (
                        <button key={oi} type="button" onClick={() => select(oi)}
                          disabled={answered}
                          onMouseEnter={() => setHovered(oi)}
                          onMouseLeave={() => setHovered((h) => (h === oi ? null : h))}
                          className={`w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium border-2 transition-colors ${!answered ? "active:scale-[0.98] cursor-pointer" : ""}`}
                          style={{ borderColor, backgroundColor: bg, color: "var(--foreground)", opacity: answered && !isThis && !isRight ? 0.45 : 1 }}>
                          <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                            style={{ backgroundColor: dotBg, color: dotColor }}>
                            {String.fromCharCode(65 + oi)}
                          </span>
                          <span dangerouslySetInnerHTML={{ __html: _md(opt) }} />
                        </button>
                      );
                    })}
                  </div>
                  {/* Feedback */}
                  {answered && (
                    <div className="text-sm font-semibold px-4 py-2.5 rounded-xl"
                      style={isCorrect
                        ? { color: "#1a8a5c", backgroundColor: "rgba(26,138,92,0.08)" }
                        : { color: "#d4453a", backgroundColor: "rgba(212,69,58,0.07)" }}>
                      {isCorrect ? `✓ ${t("common.correctShort")}` : `✗ ${t("common.wrongShort")}`}
                    </div>
                  )}
                  {/* Why that form is the right one. Only the grammar quiz fills this,
                      the content quiz leaves it empty — and for a form exercise the
                      reason IS the learning, so it must not stay hidden. */}
                  {answered && card.explanation && (
                    <p className="text-xs leading-relaxed -mt-2" style={{ color: "var(--muted)" }}>
                      <span dangerouslySetInnerHTML={{ __html: _md(card.explanation) }} />{" "}
                      {/* The rule comes from the model, the sentence came from the material. */}
                      <HelpTooltip text={t("common.aiKnowledgeHint")} />
                    </p>
                  )}
                  {/* The hint sits above the sources and below the options, where the eye already is after reading the task. */}
                  {showHint && card.extras?.tip && <HintCard text={card.extras.tip} />}
                  {/* Source chips + Hint */}
                  <div className="flex items-center justify-between mt-1 gap-2">
                    <div className="min-w-0">
                      {(() => {
                        const cardSource = card.source_label ? { source_label: card.source_label, page_number: card.page_number, start_time: card.start_time } : null;
                        const rawSrcs: ExerciseItemSource[] = card.sources?.length ? card.sources as ExerciseItemSource[] : cardSource ? [cardSource] : [];
                        const seenKeys = new Set<string>();
                        const srcs = rawSrcs.filter((s) => {
                          const k = _sourceChipKey(s.source_label, s.page_number, s.start_time, s.highlight_text);
                          if (seenKeys.has(k)) return false;
                          seenKeys.add(k);
                          return true;
                        });
                        if (!srcs.length) return null;
                        return (
                          <div className="flex flex-col gap-1">
                            <div className="flex items-center gap-1 flex-wrap">
                              {srcs.map((s, si) => {
                                const ChipIcon = _getChipIcon(s.source_label);
                                return (
                                  <button key={si} type="button"
                                    onClick={() => { if (onSourceClick) onSourceClick(s.source_label, s.page_number ?? 1, s.start_time, s.highlight_text || `${card.front} ${card.back}`); }}
                                    className="chip-cite inline-flex items-center gap-0.5 text-3xs font-medium px-2 py-1 rounded-full border-none cursor-pointer transition-colors"
                                    style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
                                    <ChipIcon size={10} weight="bold" /> {sourceTag(s.source_label, srcNumbers)}{_chunkLabel(s.source_label, s.page_number, s.start_time, (key, vals) => tChip(key, vals))}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                    {!answered && showChatHelp && (
                      <div className="flex items-center gap-2 shrink-0">
                        {(
                          <button type="button" onClick={requestHint}
                            disabled={hintLoading} aria-expanded={showHint}
                            title={showHint ? t("common.hintHide") : t("common.hint")}
                            className="btn-soft-accent flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full transition-all disabled:opacity-50">
                            <Lightbulb size={13} weight="bold" />
                            {hintLoading ? t("common.loading") : t("common.hint")}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                  {answered && showChatHelp && (
                    <div className="flex items-center justify-start mt-2">
                      <button type="button" onClick={() => {
                        onAskChat(isGap
                          ? promptTermDeep(card.back)
                          : promptTopicDeep(card.front));
                      }}
                        className="btn-soft-accent flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full transition-all">
                        <Chat size={13} weight="bold" /> {t("common.learnMore")}
                      </button>
                    </div>
                  )}
                </div>
              </div>
              {/* Back and next are always there, even unanswered: skip a task and return later; answered ones are locked, unanswered stay open. */}
              <ExerciseNav index={index} total={total}
                onPrev={() => goTo(index - 1)} onNext={advance}
                backLabel={t("common.back")} nextLabel={t("common.next")} finishLabel={t("common.finish")} />
            </div>

            {/* Follows the growing block and therefore always lands at the bottom. */}
            <div className="mx-auto w-full shrink-0 pt-5" style={{ maxWidth: 560 }}>
              <SetSourceLegend
                sources={exerciseSet.sources}
                items={exerciseSet.items}
                onSourceClick={(f) => onSourceClick?.(f, 1)}
              />
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
