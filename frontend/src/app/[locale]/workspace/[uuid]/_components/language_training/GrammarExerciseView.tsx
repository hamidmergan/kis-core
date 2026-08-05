import React, { useContext, useEffect, useMemo, useRef, useState } from "react";
import { CaretLeft, CaretRight, Check, Minus, SidebarSimple, X } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import type { ExerciseItem, ExerciseItemSource, ExerciseSet, GrammarCheckResult } from "../../_types";
import { _chunkLabel, _getChipIcon, _sourceChipKey } from "../../_utils";
import { SetSourceLegend, sourceNumbers, sourceTag } from "./SetSourceLegend";
import { MinimizeContext } from "../../_context";
import { _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";

const TITLE_PREFIX_RE = /^(Grammatik-Übung|Grammar exercise)\s*(aus|von|from|of)\s*/i;

const VERDICT_STYLE: Record<GrammarCheckResult["verdict"], { fg: string; bg: string }> = {
  correct: { fg: "#1a8a5c", bg: "rgba(26,138,92,0.08)" },
  close: { fg: "#b07d1a", bg: "rgba(176,125,26,0.10)" },
  wrong: { fg: "#d4453a", bg: "rgba(212,69,58,0.07)" },
};

/**
 * Grammatik-Übung: ein Satz je Schritt, vier Darreichungsformen gemischt.
 *
 * Die Ansicht unterscheidet sie an genau einem Merkmal, nämlich ob die Aufgabe
 * ``options`` mitbringt:
 *
 * * mit Optionen wird angekreuzt, und das entscheidet der Browser selbst,
 * * ohne Optionen wird getippt (Umformung oder Lückentext), und das kann nur das
 *   Backend beurteilen. Nur eine abweichende Antwort kostet dort einen Modellaufruf,
 *   deshalb bleibt der Knopf auch bei einer richtigen Antwort flott.
 *
 * Das Musterpaar steht an der Aufgabe, die eines braucht, nicht mehr über dem Set:
 * ein gemischtes Set hat kein gemeinsames Muster, und eine Richtig/Falsch-Aufgabe
 * folgt keinem.
 */
export function GrammarExerciseView({
  exerciseSet, workspaceUuid, onBack, onAnswer, onSourceClick, breadcrumbs, onFinish,
}: {
  exerciseSet: ExerciseSet;
  workspaceUuid: string;
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number) => void;
  breadcrumbs?: BreadcrumbItem[];
  onFinish?: (correct: number, total: number) => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const tChip = useTranslations("sourceChip");
  const minimize = useContext(MinimizeContext);

  // Grammar sentences are a numbered worksheet, so they keep their generated order
  // instead of being shuffled like flashcards.
  const items: ExerciseItem[] = useMemo(() => exerciseSet.items || [], [exerciseSet.items]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState(false);
  const [result, setResult] = useState<GrammarCheckResult | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);

  const total = items.length;
  const card = items[index];
  const answered = result !== null;

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
      setResult(data);
      const isCorrect = data.verdict === "correct";
      if (isCorrect) setCorrectCount((c) => c + 1);
      onAnswer(card.id, isCorrect);
    } catch {
      // The learner keeps the sentence and can try again; nothing is recorded.
      setResult(null);
      setCheckError(true);
    } finally {
      setChecking(false);
    }
  }

  function advance() {
    if (index >= total - 1) {
      onFinish?.(correctCount, total);
      return;
    }
    setIndex((i) => i + 1);
    setAnswer("");
    setPicked(null);
    setResult(null);
    setCheckError(false);
  }

  function skip() {
    if (!card || answered) return;
    onAnswer(card.id, false);
    setResult({ verdict: "wrong", feedback: null, solution: card.back, explanation: card.explanation });
  }

  /** Ankreuzen entscheidet der Browser: die Lösung steht in der Aufgabe. */
  function pick(optionIndex: number) {
    if (!card || answered) return;
    setPicked(optionIndex);
    const isCorrect = optionIndex === card.correct_idx;
    if (isCorrect) setCorrectCount((c) => c + 1);
    onAnswer(card.id, isCorrect);
    setResult({
      verdict: isCorrect ? "correct" : "wrong",
      feedback: null, solution: card.back, explanation: card.explanation,
    });
  }

  if (!card) return (
    <div className="flex flex-col h-full items-center justify-center gap-3">
      <Spinner size="lg" />
      <p className="text-xs">{t("common.loading")}</p>
    </div>
  );

  const progressPct = ((index + 1) / total) * 100;
  // Ankreuzen oder Tippen: genau ein Merkmal entscheidet es.
  const isChoice = Boolean(card.options?.length);
  // Das Muster haengt an der Aufgabe, die eines braucht (die Umformung).
  const pattern = card.extras?.pattern_front && card.extras?.pattern_back
    ? { front: card.extras.pattern_front, back: card.extras.pattern_back }
    : null;
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
  // Numbering belongs to the set, not to the card, so a file keeps its number across
  // every sentence and matches the legend at the bottom.
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
                    <button type="button" onClick={b.onClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={{ backgroundColor: bBadge.bg, color: bBadge.color }}>{b.label}</button>
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
          <div className="text-center text-xs font-semibold">{index + 1} / {total}</div>

          {/* The sentence to transform */}
          <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: "var(--surface)", boxShadow: "0 4px 20px rgba(0,40,60,0.08)" }}>
            <div className="px-6 pt-5 pb-6 flex flex-col gap-3">
              <div className="text-2xs font-bold" style={{ color: "var(--muted)" }}>
                {t("grammar.sentenceNo", { no: index + 1 })}
              </div>
              {/* Aufgabenzeile und Satz. Die Ankreuz-Aufgabe bringt ihre Anweisung
                  fett in front mit, deshalb wird hier Markdown-Fett gerendert. */}
              <p className="text-base font-semibold leading-snug whitespace-pre-line" style={{ color: "var(--foreground)" }}
                dangerouslySetInnerHTML={{ __html: card.front.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>") }} />

              {/* Das Muster, direkt an der Aufgabe, die eines braucht. Es steht unter
                  dem Satz und nicht darüber: der Lernende liest erst die Aufgabe. */}
              {pattern && (
                <div className="rounded-xl px-3 py-2" style={{ backgroundColor: "var(--surface-dim)" }}>
                  <p className="text-xs leading-relaxed" style={{ color: "var(--foreground-soft)" }}>{pattern.front}</p>
                  {/* Der Pfeil trägt die Richtung ohne Wort und braucht keine
                      Übersetzung. Für einen Screenreader nur Zierde. */}
                  <p className="text-xs leading-relaxed flex gap-1.5" style={{ color: "var(--foreground-soft)" }}>
                    <span aria-hidden="true" className="shrink-0" style={{ color: "var(--kb)" }}>→</span>
                    <span>{pattern.back}</span>
                  </p>
                </div>
              )}

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
                  onChange={(e) => { setAnswer(e.target.value); setCheckError(false); }}
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

              {checkError && (
                <p className="text-xs" style={{ color: "#d4453a" }}>{t("grammar.checkFailed")}</p>
              )}

              {!answered && !isChoice && (
                <div className="flex items-center gap-2">
                  <button type="button" onClick={skip}
                    className="text-xs font-medium px-3 py-1.5 rounded-full transition-colors hover:bg-[var(--surface-dim)]"
                    style={{ color: "var(--muted)" }}>
                    {t("common.dontKnow")}
                  </button>
                  <button type="button" onClick={check} disabled={checking || !answer.trim()}
                    className="btn-fill-accent flex-1 flex items-center justify-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold transition-all disabled:opacity-50">
                    {checking ? <Spinner size="sm" /> : null}
                    {checking ? t("grammar.checking") : t("grammar.check")}
                  </button>
                </div>
              )}

              {result && verdictStyle && (
                <div className="rounded-xl px-4 py-3 text-sm" style={{ backgroundColor: verdictStyle.bg, color: verdictStyle.fg }}>
                  <div className="flex items-center gap-1.5 font-bold">
                    <VerdictIcon size={14} weight="bold" /> {verdictLabel}
                  </div>
                  {result.verdict !== "correct" && (
                    <p className="mt-1.5 font-semibold">{t("grammar.solution", { solution: result.solution })}</p>
                  )}
                  {result.feedback && <p className="mt-1 opacity-90">{result.feedback}</p>}
                  {!result.feedback && result.explanation && <p className="mt-1 opacity-90">{result.explanation}</p>}
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

          {answered && (
            <div className="flex justify-center">
              <button type="button" onClick={advance}
                className="btn-fill-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
                {index + 1 >= total ? t("common.finish") : t("common.next")}
              </button>
            </div>
          )}

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
