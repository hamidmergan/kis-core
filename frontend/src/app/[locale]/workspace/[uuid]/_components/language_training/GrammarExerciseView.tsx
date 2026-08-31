import React, { useContext, useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight, Check, Minus, SidebarSimple, X } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import type { ExerciseItem, ExerciseItemSource, ExerciseSet, GrammarCheckResult } from "../../_types";
import { _chunkLabel, _getChipIcon, _sourceChipKey } from "../../_utils";
import { ExerciseNav } from "./ExerciseNav";
import { SetSourceLegend, sourceNumbers, sourceTag } from "./SetSourceLegend";
import { MinimizeContext } from "../../_context";
import { _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";
import { shuffleOptions } from "./_shuffle";

const TITLE_PREFIX_RE = /^(Grammatik-Übung|Grammar exercise)\s*(aus|von|from|of)\s*/i;

const VERDICT_STYLE: Record<GrammarCheckResult["verdict"], { fg: string; bg: string }> = {
  correct: { fg: "#1a8a5c", bg: "rgba(26,138,92,0.08)" },
  close: { fg: "#b07d1a", bg: "rgba(176,125,26,0.10)" },
  wrong: { fg: "#d4453a", bg: "rgba(212,69,58,0.07)" },
};

/** Four formats mixed, told apart only by whether the exercise has options. */
export function GrammarExerciseView({
  exerciseSet, workspaceUuid, onBack, onAnswer, onSourceClick, breadcrumbs, onFinish,
}: {
  exerciseSet: ExerciseSet;
  workspaceUuid: string;
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean, newRun: boolean) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number) => void;
  breadcrumbs?: BreadcrumbItem[];
  onFinish?: (correct: number, total: number) => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const tChip = useTranslations("sourceChip");
  const minimize = useContext(MinimizeContext);

  // Grammar sets keep their order, they are a numbered worksheet. Only the
  // options within a choice/cloze card are shuffled, once, so the answer
  // does not sit on the first option every time (the model tends to write it there).
  const [items, setItems] = useState<ExerciseItem[]>([]);
  const shuffledRef = useRef(false);
  useEffect(() => {
    const raw = exerciseSet.items || [];
    if (raw.length > 0 && !shuffledRef.current) {
      setItems(raw.map(shuffleOptions));
      shuffledRef.current = true;
    }
  }, [exerciseSet.items]);
  const [index, setIndex] = useState(0);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState(false);
  // Collapsed: the pattern is help on demand, not part of the exercise.
  const [showPattern, setShowPattern] = useState(false);

  // Everything per exercise, only that way can you go back and forth.
  const [results, setResults] = useState<Record<number, GrammarCheckResult>>({});
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [drafts, setDrafts] = useState<Record<number, string>>({});

  const total = items.length;
  const card = items[index];
  const result = card ? results[card.id] ?? null : null;
  const answered = result !== null;
  const answer = card ? drafts[card.id] ?? "" : "";
  const picked = card ? picks[card.id] ?? null : null;
  const correctCount = Object.values(results).filter((r) => r.verdict === "correct").length;

  // Typed and ticked share the same round marker.
  const runGemeldetRef = useRef(false);

  function melden(itemId: number, correct: boolean) {
    const neuerDurchgang = !runGemeldetRef.current;
    runGemeldetRef.current = true;
    onAnswer(itemId, correct, neuerDurchgang);
  }

  async function check() {
    if (!card || checking || answered || !answer.trim()) return;
    setChecking(true);
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/exercise-sets/${exerciseSet.id}/items/${card.id}/check`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer }),
        },
      );
      if (!res.ok) throw new Error("check failed");
      const data: GrammarCheckResult = await res.json();
      setResults((r) => ({ ...r, [card.id]: data }));
      melden(card.id, data.verdict === "correct");
    } catch {
      // The learner keeps the sentence and can try again; nothing is recorded.
      setCheckError(true);
    } finally {
      setChecking(false);
    }
  }

  function goTo(next: number) {
    setIndex(next);
    setShowPattern(false);
    setCheckError(false);
  }

  function advance() {
    if (index >= total - 1) {
      onFinish?.(correctCount, total);
      return;
    }
    goTo(index + 1);
  }

  /** The browser decides multiple choice, the answer sits in the exercise. */
  function pick(optionIndex: number) {
    if (!card || answered) return;
    setPicks((p) => ({ ...p, [card.id]: optionIndex }));
    const isCorrect = optionIndex === card.correct_idx;
    melden(card.id, isCorrect);
    setResults((r) => ({
      ...r,
      [card.id]: {
        verdict: isCorrect ? "correct" : "wrong",
        solution: card.back, explanation: card.explanation,
      },
    }));
  }

  if (!card) return (
    <div className="flex flex-col h-full items-center justify-center gap-3">
      <Spinner size="lg" />
      <p className="text-xs">{t("common.loading")}</p>
    </div>
  );

  const progressPct = ((index + 1) / total) * 100;
  // Multiple choice or typing: exactly one feature decides it.
  const isChoice = Boolean(card.options?.length);
  // The pattern hangs on the exercise that needs one, the reshaping.
  const pattern = card.extras?.pattern_front && card.extras?.pattern_back
    ? { front: card.extras.pattern_front, back: card.extras.pattern_back }
    : null;
  // The instruction belongs above the card, the sentence inside it.
  const [taskLine, sentence] = (() => {
    const m = card.front.match(/^\*\*(.+?)\*\*\n\n([\s\S]+)$/);
    return m ? [m[1], m[2]] : ["", card.front];
  })();
  const verdictStyle = result ? VERDICT_STYLE[result.verdict] : null;
  const VerdictIcon = result?.verdict === "correct" ? Check : result?.verdict === "close" ? Minus : X;
  const verdictLabel = result
    ? t(`grammar.verdict.${result.verdict}` as "grammar.verdict.correct")
    : "";

  const cardSource = card.source_label
    ? { source_label: card.source_label, page_number: card.page_number, start_time: card.start_time }
    : null;
  const rawSrcs: ExerciseItemSource[] = card.sources?.length
    ? (card.sources as ExerciseItemSource[])
    : cardSource ? [cardSource] : [];
  const seenKeys = new Set<string>();
  const srcs = rawSrcs.filter((s) => {
    const k = _sourceChipKey(s.source_label, s.page_number, s.start_time, s.highlight_text);
    if (seenKeys.has(k)) return false;
    seenKeys.add(k);
    return true;
  });
  // The numbering belongs to the set so it matches the legend.
  const srcNumbers = sourceNumbers(exerciseSet.sources);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
        <button type="button" onClick={onBack}
          className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          style={{ backgroundColor: "var(--surface-dim)" }}>
          <CaretLeft size={13} />
        </button>
        {breadcrumbs && breadcrumbs.length > 0 ? (
          <div className="flex items-center gap-1 text-xs min-w-0 flex-1">
            {breadcrumbs.map((b, i) => {
              const bBadge = _getToolBadge(b.toolKey, "language_training");
              return (
                <React.Fragment key={i}>
                  {bBadge ? (
                    <button type="button" onClick={b.onClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={{ color: bBadge.color }}>{b.label}</button>
                  ) : (
                    <button type="button" onClick={b.onClick} className="font-medium shrink-0 opacity-60 hover:opacity-100 transition-opacity" style={{ color: "var(--muted)" }}>{b.label}</button>
                  )}
                  <CaretRight size={9} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" />
                </React.Fragment>
              );
            })}
            <span className="font-semibold truncate" style={{ color: "var(--foreground)" }}>{exerciseSet.title.replace(TITLE_PREFIX_RE, "")}</span>
          </div>
        ) : (
          <span className="text-xs font-semibold flex-1 truncate" style={{ color: "var(--foreground)" }}>{exerciseSet.title.replace(TITLE_PREFIX_RE, "")}</span>
        )}
        {minimize && (
          <button type="button" onClick={minimize}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title={t("common.minimizePanel")}>
            <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
          </button>
        )}
      </div>

      {/* Progress */}
      <div className="w-full" style={{ height: 3, backgroundColor: "var(--border)" }}>
        <div className="h-full transition-all duration-500 rounded-r-full" style={{ width: `${progressPct}%`, backgroundColor: "var(--kb)" }} />
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto mt-1 sm:mt-3 w-full flex flex-col gap-3" style={{ maxWidth: 560 }}>
          {/* Welches Thema geübt wird. In der Liste steht es auf der Karte, beim Üben
              fehlte es: die Anweisung nennt zwar die Form, aber erst ab der zweiten
              Aufgabe weiss man, dass sie für das ganze Set gilt. Gleiche Machart wie
              das Abzeichen in der Übersicht. */}
          {exerciseSet.grammar_topic_name && (
            <div className="flex items-center gap-2">
              <span className="text-3xs font-semibold px-1.5 py-0.5 rounded"
                style={{ backgroundColor: "rgba(var(--kb-rgb),0.10)", color: "var(--kb)" }}>
                {exerciseSet.grammar_topic_name}
              </span>
            </div>
          )}

          {/* The sentence to transform */}
          <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: "var(--surface)", boxShadow: "0 4px 20px rgba(0,40,60,0.08)" }}>
            <div className="px-6 pt-5 pb-6 flex flex-col gap-3">
              {/* Anweisung direkt über dem Satz, auf den sie sich bezieht. Sie wechselt
                  mit der Aufgabe, denn ein gemischtes Set hat keine gemeinsame. Fett
                  hebt sie ab, ohne den Satz zu überstimmen. */}
              {taskLine && (
                <p className="text-sm font-bold leading-snug" style={{ color: "var(--foreground)" }}>{taskLine}</p>
              )}
              <p className="text-sm leading-snug whitespace-pre-line" style={{ color: "var(--foreground)" }}>{sentence}</p>

              {isChoice ? (
                <div className="flex flex-col gap-1.5">
                  {(card.options || []).map((opt, oi) => {
                    const isRight = oi === card.correct_idx;
                    const chosen = picked === oi;
                    const show = answered && (isRight || chosen);
                    return (
                      <button key={oi} type="button" onClick={() => pick(oi)} disabled={answered}
                        className="text-left px-3 py-2 rounded-xl text-sm border-2 transition-colors disabled:cursor-default"
                        style={{
                          borderColor: show ? (isRight ? "#1a8a5c" : "#d4453a") : "var(--border)",
                          backgroundColor: show
                            ? (isRight ? "rgba(26,138,92,0.08)" : "rgba(212,69,58,0.07)")
                            : "transparent",
                          color: "var(--foreground)",
                        }}>
                        {opt}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <textarea
                  value={answer}
                  onChange={(e) => { setDrafts((d) => ({ ...d, [card.id]: e.target.value })); setCheckError(false); }}
                  onKeyDown={(e) => {
                    // Enter checks, Shift+Enter keeps the newline for long sentences.
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void check(); }
                  }}
                  disabled={answered || checking}
                  rows={3}
                  spellCheck={false}
                  placeholder={t("grammar.answerPlaceholder")}
                  className="w-full rounded-xl px-3 py-2.5 text-sm resize-y bg-background text-foreground border-2 border-border transition-colors enabled:hover:border-kb focus:border-kb focus:outline-none disabled:opacity-75"
                />
              )}

              {/* Das Muster, eingeklappt und unter der Eingabe.
                  Offen und über der Eingabe stand es dem Satz im Weg und lud zum
                  Abschreiben ein. Wer nicht weiterweiss, klappt es auf. */}
              {pattern && (
                <div>
                  <button type="button" onClick={() => setShowPattern((v) => !v)}
                    aria-expanded={showPattern}
                    className="inline-flex items-center gap-1 text-xs font-medium transition-colors hover:text-kb"
                    style={{ color: "var(--muted)" }}>
                    <CaretRight size={10} weight="bold"
                      className={`transition-transform ${showPattern ? "rotate-90" : ""}`} />
                    {t("grammar.example")}
                  </button>
                  {showPattern && (
                    <div className="mt-1.5 rounded-xl px-3 py-2" style={{ backgroundColor: "var(--surface-dim)" }}>
                      {/* Gleiche Groesse wie der Satz in der Aufgabe und wie die
                          Erklaerung nach dem Pruefen: alles, was der Lernende LIEST,
                          liest sich auf einer Stufe. Klein bleiben nur die Bedienteile. */}
                      <p className="text-sm leading-relaxed" style={{ color: "var(--foreground-soft)" }}>{pattern.front}</p>
                      {/* Der Pfeil trägt die Richtung ohne Wort und braucht keine
                          Übersetzung. Für einen Screenreader nur Zierde. */}
                      <p className="text-sm leading-relaxed flex gap-1.5" style={{ color: "var(--foreground-soft)" }}>
                        <span aria-hidden="true" className="shrink-0" style={{ color: "var(--kb)" }}>→</span>
                        <span>{pattern.back}</span>
                      </p>
                    </div>
                  )}
                </div>
              )}

              {checkError && (
                <p className="text-xs" style={{ color: "#d4453a" }}>{t("grammar.checkFailed")}</p>
              )}

              {!answered && !isChoice && (
                <button type="button" onClick={check} disabled={checking || !answer.trim()}
                  className="btn-fill-accent w-full flex items-center justify-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold transition-all disabled:opacity-50">
                  {checking ? <Spinner size="sm" /> : null}
                  {checking ? t("grammar.checking") : t("grammar.check")}
                </button>
              )}

              {result && verdictStyle && (
                <div className="rounded-xl px-4 py-3 text-sm" style={{ backgroundColor: verdictStyle.bg, color: verdictStyle.fg }}>
                  <div className="flex items-center gap-1.5 font-bold">
                    <VerdictIcon size={14} weight="bold" /> {verdictLabel}
                  </div>
                  {result.verdict !== "correct" && (
                    <p className="mt-1.5 font-semibold">{t("grammar.solution", { solution: result.solution })}</p>
                  )}
                  {result.explanation && <p className="mt-1 opacity-90">{result.explanation}</p>}
                </div>
              )}

              {/* Source chips: nav-only, same behaviour as chat citations */}
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
                          <ChipIcon size={10} weight="bold" /> {sourceTag(s.source_label, srcNumbers)}{_chunkLabel(s.source_label, s.page_number, s.start_time, (key, vals) => tChip(key, vals))}
                        </button>
                      );
                    })}
                  </div>
                  {/* No filename list per card: the numbered legend at the bottom of
                      the view names every source once, for the whole set. */}
                </div>
              )}

            </div>
          </div>

          {/* Zurueck und Weiter stehen immer da, auch unbeantwortet: wer eine Aufgabe
              nicht loesen kann, blaettert weiter und kommt spaeter zurueck. Beantwortete
              sind dann gesperrt, unbeantwortete weiter offen. */}
          <ExerciseNav index={index} total={total}
            onPrev={() => goTo(index - 1)} onNext={advance}
            backLabel={t("common.back")} nextLabel={t("common.next")} finishLabel={t("common.finish")} />

          <SetSourceLegend
            sources={exerciseSet.sources}
            onSourceClick={(f) => onSourceClick?.(f, 1)}
            className="pt-1"
          />
        </div>
      </div>
    </div>
  );
}
