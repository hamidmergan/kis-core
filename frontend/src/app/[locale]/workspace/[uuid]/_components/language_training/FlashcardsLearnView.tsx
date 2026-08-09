import React, { useContext, useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight, Chat, Check, Lightbulb, Question, SidebarSimple, XIcon } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import type { ExerciseItem, ExerciseItemSource, ExerciseSet, Source } from "../../_types";
import { _chunkLabel, _getChipIcon, _md, _sourceChipKey } from "../../_utils";
import { MinimizeContext } from "../../_context";
import { _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";
import { ExerciseNav } from "./ExerciseNav";
import { SetSourceLegend, sourceNumbers, sourceTag } from "./SetSourceLegend";

export function FlashcardsLearnView({
  exerciseSet, onBack, onAnswer, onAskChat, onSourceClick, breadcrumbs, showTranslation, chatLang = "de",
}: {
  exerciseSet: ExerciseSet;
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean) => void;
  onAskChat?: (text: string) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number) => void;
  breadcrumbs?: BreadcrumbItem[];
  showTranslation?: boolean;
  chatLang?: "de" | "en";
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const tChip = useTranslations("sourceChip");
  // Chat prompt strings are sent to the LLM, not displayed. They follow the UI
  // locale (the language picked in the header) so a hint/learn-more for an
  // English card is asked — and answered — in English. chatLang stays in the
  // prop signature for callers but no longer drives these prompts.
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
      if (exerciseSet.tool === "flashcards") {
        setShuffledItems(raw);
      } else {
        const arr = [...raw];
        for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[arr[i], arr[j]] = [arr[j], arr[i]]; }
        setShuffledItems(arr);
      }
      shuffledRef.current = true;
    }
  }, [exerciseSet.items, exerciseSet.tool]);
  const items = shuffledItems;
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [results, setResults] = useState<Record<number, boolean>>({});
  const [streak, setStreak] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [showPendingPrompt, setShowPendingPrompt] = useState(false);

  const total = items.length;
  const card = items[index];
  const isVocab = exerciseSet.tool === "flashcards";
  // Schon bewertet? Dann sind die beiden Urteilsknoepfe gesperrt.
  const rated = Boolean(card && card.id in results);
  // Chip numbering belongs to the SET, so a file keeps its number on every card
  // and matches the numbered legend at the bottom of the view.
  const srcNumbers = sourceNumbers(exerciseSet.sources);

  useEffect(() => { setFlipped(false); }, [index]);

  function answer(correct: boolean) {
    // Eine bewertete Karte bleibt bewertet. Wer zurueckblaettert, sieht sein Urteil
    // und kann es nicht mehr aendern, offene Karten bleiben offen.
    if (!card || card.id in results) return;
    setResults((r) => ({ ...r, [card.id]: correct }));
    if (correct) setStreak((s) => s + 1);
    else setStreak(0);
    onAnswer(card.id, correct);
  }

  function goTo(next: number) {
    setIndex(next);
    setFlipped(false);
  }

  function advance() {
    if (index < total - 1) {
      goTo(index + 1);
      return;
    }
    const pending = items.filter((it) => !(it.id in results));
    if (pending.length > 0) setShowPendingPrompt(true);
    else setShowResults(true);
  }

  function goToFirstPending() {
    const firstPendingIdx = items.findIndex(it => !(it.id in results));
    if (firstPendingIdx >= 0) {
      setIndex(firstPendingIdx);
      setFlipped(false);
    }
    setShowPendingPrompt(false);
  }

  function finishAnyway() {
    setShowPendingPrompt(false);
    setShowResults(true);
  }

  if (!card && !showResults) return (
    <div className="flex flex-col h-full items-center justify-center gap-3">
      <Spinner size="lg" />
      <p className="text-xs" >{t("common.loading")}</p>
    </div>
  );
  const progressPct = showResults ? 100 : ((index + 1) / total) * 100;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
        <button type="button" onClick={onBack}
          className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          style={{ backgroundColor: "var(--surface-dim)" }}>
          <CaretLeft size={13} />
        </button>
        {breadcrumbs && breadcrumbs.length > 0 ? (<div className="flex items-center gap-1 text-xs min-w-0 flex-1">{breadcrumbs.map((b, i) => { const bBadge = _getToolBadge(b.toolKey, isVocab ? "language_training" : "learning_tools"); return (<React.Fragment key={i}>{bBadge ? (<button type="button" onClick={b.onClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={{ backgroundColor: bBadge.bg, color: bBadge.color }}>{b.label}</button>) : (<button type="button" onClick={b.onClick} className="font-medium shrink-0 opacity-60 hover:opacity-100 transition-opacity" style={{ color: "var(--muted)" }}>{b.label}</button>)}<CaretRight size={9} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" /></React.Fragment>); })}<span className="font-semibold truncate" style={{ color: "var(--foreground)" }}>{exerciseSet.title.replace(/^(Lernkarten|Grammatik-Übung|Quiz)\s*(aus|von)\s*/i, "")}</span></div>) : (<span className="text-xs font-semibold flex-1 truncate" style={{ color: "var(--foreground)" }}>{exerciseSet.title.replace(/^(Lernkarten|Grammatik-Übung|Quiz)\s*(aus|von)\s*/i, "")}</span>)}
        {minimize && (
          <button type="button" onClick={minimize}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title={t("common.minimizePanel")}>
            <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
          </button>
        )}
      </div>
      {/* Progress bar as top border */}
      <div className="w-full" style={{ height: 3, backgroundColor: "var(--border)" }}>
        <div className="h-full transition-all duration-500 rounded-r-full" style={{ width: `${progressPct}%`, backgroundColor: "var(--kb)" }} />
      </div>
      {/* Results */}
      {showResults ? (
        <div className="flex-1 flex flex-col items-center justify-center px-6 gap-3">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
            style={{ backgroundColor: "#1a8a5c", boxShadow: "0 4px 20px rgba(26,138,92,0.25)" }}>
            <Check size={30} weight="bold" color="white" />
          </div>
          <h3 className="text-lg font-semibold">{t("common.completed")}</h3>
          {isVocab ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {t.rich("flashcardsLearn.vocabSummary", {
                count: total,
                hl: (chunks) => <strong style={{ color: "#1a8a5c" }}>{chunks}</strong>,
              })}
            </p>
          ) : (() => {
            const correctCount = Object.values(results).filter(Boolean).length;
            const wrongCount = Object.values(results).filter(v => v === false).length;
            const pendingCount = total - Object.keys(results).length;
            const pct = total > 0 ? Math.round((correctCount / total) * 100) : 0;
            return (
              <p className="text-sm text-center" style={{ color: "var(--muted)" }}>
                {t.rich("completion.score", {
                  correct: correctCount,
                  total,
                  pct,
                  hl: (chunks) => <strong style={{ color: "#1a8a5c" }}>{chunks}</strong>,
                })}
                {(wrongCount > 0 || pendingCount > 0) && (
                  <>
                    <br />
                    <span className="text-xs" >
                      {wrongCount > 0 && t("flashcardsLearn.wrongCount", { count: wrongCount })}
                      {wrongCount > 0 && pendingCount > 0 && ", "}
                      {pendingCount > 0 && t("flashcardsLearn.pendingCount", { count: pendingCount })}
                    </span>
                  </>
                )}
              </p>
            );
          })()}
          <div className="flex gap-3 mt-4">
            <button type="button" onClick={() => { setShowResults(false); setIndex(0); setFlipped(false); setResults({}); setShowPendingPrompt(false); shuffledRef.current = false; }}
              className="btn-outline-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
              {t("common.again")}
            </button>
            <button type="button" onClick={onBack}
              className="btn-fill-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
              {t("common.done")}
            </button>
          </div>
        </div>
      ) : showPendingPrompt ? (() => {
        const pendingCount = total - Object.keys(results).length;
        return (
          <div className="flex-1 flex flex-col items-center justify-center px-6 gap-3">
            <div className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
              style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)" }}>
              <Question size={30} weight="bold" style={{ color: "var(--kb)" }} />
            </div>
            <h3 className="text-lg font-semibold text-center">{t("flashcardsLearn.pendingTitle")}</h3>
            <p className="text-sm text-center" style={{ color: "var(--muted)" }}>
              {t.rich("flashcardsLearn.pendingBody", {
                count: pendingCount,
                kb: (chunks) => <strong style={{ color: "var(--kb)" }}>{chunks}</strong>,
              })}
            </p>
            <div className="flex flex-wrap gap-3 mt-4 justify-center">
              <button type="button" onClick={goToFirstPending}
                className="btn-fill-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
                {t("flashcardsLearn.viewPending")}
              </button>
              <button type="button" onClick={finishAnyway}
                className="btn-outline-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
                {t("flashcardsLearn.finishAnyway")}
              </button>
            </div>
          </div>
        );
      })() : card ? (() => {
        const cardSource = card.source_label ? { source_label: card.source_label, page_number: card.page_number, start_time: card.start_time } : null;

        // ── Flashcards: single-page card, no flip ──
        if (isVocab) {
          const definition = (card.back || "").trim();
          const wordParts = card.extras?.word_parts?.trim() || "";
          const wordPartsExplained = card.extras?.word_parts_explained?.trim() || "";
          const exampleSentence = card.extras?.example_sentence?.trim() || "";
          const wordClass = card.extras?.word_class?.trim() || "";
          const singular = card.extras?.singular?.trim() || "";
          const plural = card.extras?.plural?.trim() || "";
          // A noun without a plural (Wasser, Hunger) keeps its singular under the neutral
          // label "Form", because the article is the point. A lone "Singular" row would
          // promise a "Plural" row that never comes. A plural without a singular is dropped.
          const showNumberPair = Boolean(singular && plural);
          const showFormOnly = Boolean(singular && !plural);
          return <>
            <div className="flex-1 overflow-y-auto px-3 sm:px-4 pt-4 sm:pt-6 pb-3">
              <div className="mx-auto w-full flex flex-col gap-3" style={{ maxWidth: 560 }}>
                <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: "var(--surface)", boxShadow: "0 4px 20px rgba(0,0,0,0.07)" }}>
                  <div className="p-5 flex flex-col gap-4">
                    {/* Term */}
                    <div className="text-center">
                      <p className="text-lg leading-relaxed font-semibold" style={{ color: "var(--foreground)" }}>{card.front}</p>
                      {showTranslation && card.back_en && (
                        <p className="text-sm italic mt-0.5" >{t("flashcardsLearn.translationPrefix")} {card.back_en}</p>
                      )}
                    </div>
                    {/* Definition */}
                    <div>
                      <span className="text-3xs font-bold uppercase tracking-widest" >{t("flashcardsLearn.definition")}</span>
                      <p className="text-base leading-relaxed mt-1" style={{ color: "var(--foreground)" }}>{definition}</p>
                    </div>
                    {/* Word parts */}
                    {wordParts && (() => {
                      const parts = wordPartsExplained.split("|").map(p => p.trim()).filter(Boolean);
                      return (
                        <div className="px-3 py-2.5 rounded-xl" style={{ backgroundColor: "var(--surface-dim)" }}>
                          <span className="text-3xs font-bold uppercase tracking-widest" >{t("flashcardsLearn.wordParts")}</span>
                          <p className="text-base font-semibold mt-1.5" style={{ color: "var(--foreground)" }}>{wordParts}</p>
                          {parts.length > 0 && (
                            <div className="flex flex-col gap-1 mt-2">
                              {parts.map((part, pi) => {
                                const [term, ...rest] = part.split("=");
                                const explanation = rest.join("=").trim();
                                return (
                                  <div key={pi} className="flex items-baseline gap-1.5 text-sm">
                                    <span className="font-semibold shrink-0" style={{ color: "var(--foreground)" }}>{term.trim()}</span>
                                    {explanation && <span >{explanation}</span>}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                    {/* Word class first, then the number forms when present, no box */}
                    {(wordClass || singular) && (
                      <div className="flex flex-col gap-1 px-1">
                        {wordClass && (
                          <div className="flex items-baseline gap-1.5 text-sm">
                            <span className="font-semibold shrink-0" style={{ color: "var(--foreground)" }}>{t("flashcardsLearn.wordClass")}</span>
                            <span >{wordClass}</span>
                          </div>
                        )}
                        {showNumberPair && (
                          <>
                            <div className="flex items-baseline gap-1.5 text-sm">
                              <span className="font-semibold shrink-0" style={{ color: "var(--foreground)" }}>{t("flashcardsLearn.singular")}</span>
                              <span >{singular}</span>
                            </div>
                            <div className="flex items-baseline gap-1.5 text-sm">
                              <span className="font-semibold shrink-0" style={{ color: "var(--foreground)" }}>{t("flashcardsLearn.plural")}</span>
                              <span >{plural}</span>
                            </div>
                          </>
                        )}
                        {showFormOnly && (
                          <div className="flex items-baseline gap-1.5 text-sm">
                            <span className="font-semibold shrink-0" style={{ color: "var(--foreground)" }}>{t("flashcardsLearn.form")}</span>
                            <span >{singular}</span>
                          </div>
                        )}
                      </div>
                    )}
                    {/* Context sentence */}
                    {exampleSentence && (
                      <div className="px-3 py-2.5 rounded-xl" style={{ border: "1px solid var(--border)" }}>
                        <span className="text-3xs font-bold uppercase tracking-widest" >{t("flashcardsLearn.example")}</span>
                        <p className="text-sm italic leading-relaxed mt-1" style={{ color: "var(--foreground)" }}>{exampleSentence}</p>
                      </div>
                    )}
                    {/* Sources + Chat */}
                    {(() => {
                      const rawSrcs: ExerciseItemSource[] = card.sources?.length ? card.sources as ExerciseItemSource[] : cardSource ? [cardSource] : [];
                      const seenKeys = new Set<string>();
                      const srcs = rawSrcs.filter((s) => {
                        const k = _sourceChipKey(s.source_label, s.page_number, s.start_time, s.highlight_text);
                        if (seenKeys.has(k)) return false;
                        seenKeys.add(k);
                        return true;
                      });
                      return <>
                    {srcs.length > 0 && (
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-1 flex-wrap">
                          {srcs.map((s, si) => {
                            const ChipIcon = _getChipIcon(s.source_label);
                            return (
                            <button key={si} type="button"
                              onClick={() => { if (onSourceClick) onSourceClick(s.source_label, s.page_number ?? 1, s.start_time); }}
                              className="chip-cite inline-flex items-center gap-0.5 text-3xs font-medium px-2 py-1 rounded-full border-none cursor-pointer transition-colors"
                              style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
                              <ChipIcon size={10} weight="bold" /> {sourceTag(s.source_label, srcNumbers)}{_chunkLabel(s.source_label, s.page_number ?? 1, s.start_time, (key, vals) => tChip(key, vals))}
                            </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                      </>;
                    })()}
                    <div className="flex items-center justify-end">
                      {onAskChat && (
                        <button type="button" onClick={() => onAskChat(promptTermDeep(card.front))}
                          className="btn-soft-accent inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-full transition-colors">
                          <Chat size={12} weight="bold" /> {t("common.learnMore")}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
                {/* Zurueck und Weiter. Ein Vokabelbegriff wird nicht bewertet, er gilt
                    als gesehen, sobald man ihn verlaesst. Zurueckblaettern aendert daran
                    nichts, gesehen bleibt gesehen. */}
                <ExerciseNav index={index} total={total}
                  onPrev={() => goTo(index - 1)} onNext={() => { answer(true); advance(); }}
                  backLabel={t("common.back")} nextLabel={t("flashcardsLearn.nextTerm")}
                  finishLabel={t("common.finish")} />
              </div>
            </div>
          </>;
        }

        // ── Karteikarten: flip card ──
        return <>
          <div className="flex-1 flex flex-col items-center px-3 sm:px-4 pt-4 sm:pt-6 pb-3 gap-3">
            <div className="w-full" style={{ perspective: 1200, maxWidth: 560, userSelect: "none" }}>
              <div style={{
                position: "relative", width: "100%", minHeight: 300, transformStyle: "preserve-3d",
                transition: "transform 0.5s cubic-bezier(0.4,0,0.2,1)",
                transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
              }}>
                {/* Front */}
                <div style={{
                  position: "absolute", inset: 0, backfaceVisibility: "hidden", borderRadius: 16,
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                  padding: "36px 20px", gap: 8, backgroundColor: "var(--surface)",
                  border: "1px solid var(--border)",
                  boxShadow: "0 4px 20px rgba(0,0,0,0.07)",
                }}>
                  <span className="text-3xs font-bold uppercase tracking-widest" >{t("flashcardsLearn.questionLabel")}</span>
                  <p className="text-sm text-center leading-relaxed font-semibold" style={{ color: "var(--foreground)" }} dangerouslySetInnerHTML={{ __html: _md(card.front) }} />
                  <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between">
                    <span />
                    {onAskChat && (
                      <button type="button" onClick={(e) => { e.stopPropagation(); onAskChat(promptTip(card.front)); }}
                        className="btn-soft-accent flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border-none cursor-pointer transition-colors">
                        <Lightbulb size={13} weight="bold" /> {t("common.hint")}
                      </button>
                    )}
                  </div>
                </div>
                {/* Back */}
                <div style={{
                  position: "absolute", inset: 0, backfaceVisibility: "hidden", transform: "rotateY(180deg)",
                  borderRadius: 16, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                  padding: "36px 20px 56px", gap: 8,
                  backgroundColor: "var(--kb)",
                  boxShadow: "0 4px 20px rgba(var(--kb-rgb),0.2)",
                }}>
                  <span className="text-3xs font-bold uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.35)" }}>{t("flashcardsLearn.answerLabel")}</span>
                  <p className="text-sm text-center leading-relaxed font-semibold" style={{ color: "white" }} dangerouslySetInnerHTML={{ __html: _md(card.back) }} />
                  {/* Chat button */}
                  <div className="absolute bottom-3 left-4 right-4 flex items-center justify-end">
                    {onAskChat && (
                      <button type="button" onClick={(e) => {
                        e.stopPropagation(); onAskChat(promptTopicDeep(card.front));
                      }}
                        className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border-none cursor-pointer transition-all text-white/55 bg-white/10 hover:text-white hover:bg-white/20">
                        <Chat size={13} weight="bold" /> {t("common.learnMore")}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
            {/* Actions */}
            <div className="flex flex-wrap items-center justify-center gap-3 min-h-12">
              {flipped ? (
                <>
                  <button key="again" type="button" onClick={() => answer(false)} title={t("common.again")}
                    disabled={rated}
                    className="btn-outline-danger w-11 h-11 rounded-full flex items-center justify-center disabled:opacity-40">
                    <XIcon size={18} weight="bold" />
                  </button>
                  <button key="back-to-question" type="button" onClick={() => setFlipped(false)}
                    className="btn-soft-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
                    {t("common.showQuestion")}
                  </button>
                  <button key="knew" type="button" onClick={() => answer(true)} title={t("common.know")}
                    disabled={rated}
                    className="btn-outline-success w-11 h-11 rounded-full flex items-center justify-center disabled:opacity-40">
                    <Check size={18} weight="bold" />
                  </button>
                </>
              ) : (
                <button key="show-answer" type="button" onClick={() => setFlipped(true)}
                  className="btn-soft-accent px-6 py-2 rounded-full text-xs font-semibold transition-all">
                  {t("common.showAnswer")}
                </button>
              )}
            </div>
            {/* Zurueck und Weiter stehen immer da. Wer eine Karte nicht bewerten will,
                blaettert weiter und kommt spaeter zurueck. */}
            <ExerciseNav index={index} total={total}
              onPrev={() => goTo(index - 1)} onNext={advance}
              backLabel={t("common.back")} nextLabel={t("common.next")} finishLabel={t("common.finish")} />
            {/* Source chips + filename legend */}
            {(() => {
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
                <div className="flex flex-col gap-1 w-full mt-4" style={{ maxWidth: 560 }}>
                  <div className="flex items-center gap-1 flex-wrap">
                    {srcs.map((s, si) => {
                      const ChipIcon = _getChipIcon(s.source_label);
                      return (
                      <button key={si} type="button"
                        onClick={() => { if (onSourceClick) onSourceClick(s.source_label, s.page_number ?? 1, s.start_time); }}
                        className="chip-cite inline-flex items-center gap-0.5 text-3xs font-medium px-2 py-1 rounded-full border-none cursor-pointer transition-colors"
                        style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
                        <ChipIcon size={10} weight="bold" /> {sourceTag(s.source_label, srcNumbers)}{_chunkLabel(s.source_label, s.page_number ?? 1, s.start_time, (key, vals) => tChip(key, vals))}
                      </button>
                      );
                    })}
                  </div>
                </div>
              );
            })()}

            <SetSourceLegend
              sources={exerciseSet.sources}
              onSourceClick={(f) => onSourceClick?.(f, 1)}
              className="w-full mt-3"
            />
          </div>
        </>;
      })() : null}
    </div>
  );
}
