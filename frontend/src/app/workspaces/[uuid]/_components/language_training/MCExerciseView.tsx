import React, { useContext, useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight, Chat, Check, Lightbulb, Question, SidebarSimple } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { ExerciseItem, ExerciseSet, Source } from "../../_types";
import { _chunkLabel, _getChipIcon, _md } from "../../_utils";
import { MinimizeContext } from "../../_context";
import { _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";

export function MCExerciseView({
  exerciseSet, tool, onBack, onAnswer, onAskChat, onSourceClick, breadcrumbs,
}: {
  exerciseSet: ExerciseSet;
  tool: "lueckentext" | "vokabeltest" | "quiz";
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean, newRun?: boolean) => void;
  onAskChat: (text: string) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number, highlightText?: string) => void;
  breadcrumbs?: BreadcrumbItem[];
}) {
  const minimize = useContext(MinimizeContext);
  const [shuffledItems, setShuffledItems] = useState<ExerciseItem[]>([]);
  const shuffledRef = useRef(false);
  useEffect(() => {
    const raw = exerciseSet.items || [];
    if (raw.length > 0 && !shuffledRef.current) {
      const arr = [...raw];
      for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[arr[i], arr[j]] = [arr[j], arr[i]]; }
      if (tool === "quiz") {
        const shuffled = arr.map((item) => {
          if (!item.options || item.correct_idx === undefined) return item;
          const indices = item.options.map((_, i) => i);
          for (let i = indices.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[indices[i], indices[j]] = [indices[j], indices[i]]; }
          return { ...item, options: indices.map((i) => item.options![i]), correct_idx: indices.indexOf(item.correct_idx) };
        });
        setShuffledItems(shuffled);
      } else {
        setShuffledItems(arr);
      }
      shuffledRef.current = true;
    }
  }, [exerciseSet.items, tool]);
  const items = shuffledItems;
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [results, setResults] = useState<{ item_id: number; correct: boolean }[]>([]);
  const [streak, setStreak] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [hintLoading, setHintLoading] = useState(false);

  const total = items.length;
  const card = items[index];
  const answered = selected !== null;
  const isCorrect = answered && selected === card?.correct_idx;

  function select(optIdx: number) {
    if (answered || !card) return;
    setSelected(optIdx);
    const correct = optIdx === card.correct_idx;
    const isFirst = results.length === 0;
    setResults(prev => [...prev, { item_id: card.id, correct }]);
    if (correct) setStreak((s) => s + 1);
    else setStreak(0);
    onAnswer(card.id, correct, isFirst);
  }

  function advance() {
    if (index >= total - 1) {
      if (tool === "quiz") {
        setShowResults(true);
      } else {
        onBack();
      }
    } else {
      setIndex((i) => i + 1);
      setSelected(null);
      setHint(null);
    }
  }

  async function requestHint() {
    if (!card || hintLoading) return;
    setHintLoading(true);
    try {
      onAskChat(`Gib mir einen kurzen Tipp zur folgenden Frage, OHNE die Antwort zu verraten.: „${card.front}"`);
    } catch { /* ignore */ }
    setHintLoading(false);
  }

  if (!card && !showResults) return (
    <div className="flex flex-col h-full items-center justify-center gap-3">
      <Spinner size="lg" />
      <p className="text-xs" >Wird geladen…</p>
    </div>
  );
  const progressPct = showResults ? 100 : ((index + 1) / total) * 100;
  const options = card?.options || [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
        <button type="button" onClick={onBack}
          className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          style={{ backgroundColor: "var(--surface-dim)" }}>
          <CaretLeft size={13} />
        </button>
        {breadcrumbs && breadcrumbs.length > 0 ? (<div className="flex items-center gap-1 text-[12px] min-w-0 flex-1">{breadcrumbs.map((b, i) => { const bBadge = _getToolBadge(b.toolKey, tool === "quiz" ? "learning_tools" : "language_training"); return (<React.Fragment key={i}>{bBadge ? (<button type="button" onClick={b.onClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={{ backgroundColor: bBadge.bg, color: bBadge.color }}>{b.label}</button>) : (<button type="button" onClick={b.onClick} className="font-medium shrink-0 opacity-60 hover:opacity-100 transition-opacity" style={{ color: "var(--muted)" }}>{b.label}</button>)}<CaretRight size={9} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" /></React.Fragment>); })}<span className="font-semibold truncate" style={{ color: "var(--text)" }}>{exerciseSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}</span></div>) : (<span className="text-[12px] font-semibold flex-1 truncate" style={{ color: "var(--text)" }}>{exerciseSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}</span>)}
        {minimize && (
          <button type="button" onClick={minimize}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title="Panel minimieren">
            <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
          </button>
        )}
      </div>
      {/* Progress — rendered inside question card */}
      {/* Quiz Results */}
      {showResults && tool === "quiz" ? (
        <div className="flex-1 flex flex-col items-center justify-center px-6 gap-3">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
            style={{ backgroundColor: "#1a8a5c", boxShadow: "0 4px 20px rgba(26,138,92,0.25)" }}>
            <Check size={30} weight="bold" color="white" />
          </div>
          <h3 className="text-lg font-semibold">Quiz abgeschlossen!</h3>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            <strong style={{ color: "#1a8a5c" }}>{results.filter(r => r.correct).length} / {total}</strong> richtig — <strong style={{ color: "#1a8a5c" }}>{Math.round((results.filter(r => r.correct).length / total) * 100)}%</strong>
          </p>
          <div className="flex gap-3 mt-4">
            <button type="button" onClick={() => { setShowResults(false); setIndex(0); setSelected(null); setResults([]); shuffledRef.current = false; }}
              className="btn-outline-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
              Erneut versuchen
            </button>
            <button type="button" onClick={onBack}
              className="btn-fill-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
              Fertig
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
          <div className="flex-1 overflow-y-auto p-4">
            <div className="mx-auto mt-4 sm:mt-6 w-full flex flex-col gap-3" style={{ maxWidth: 560 }}>
              <div className="text-center text-xs font-semibold" >
                {index + 1} / {total}
              </div>
              <div className="rounded-2xl flex flex-col gap-4 overflow-hidden" style={{ backgroundColor: "var(--surface)", boxShadow: "0 4px 20px rgba(0,40,60,0.08)" }}>
                <div className="px-6 pt-5 pb-6 flex flex-col gap-4">
                  {/* Question text */}
                  {tool === "lueckentext" ? (
                    <p className="text-sm leading-relaxed" style={{ color: "var(--text)" }}
                      dangerouslySetInnerHTML={{
                        __html: card.front.replace(
                          /___+/g,
                          answered
                            ? `<span style="font-weight:700;color:${isCorrect ? '#1a8a5c' : '#d4453a'};border-bottom:2px solid ${isCorrect ? '#1a8a5c' : '#d4453a'};padding:0 4px">${card.back}</span>`
                            : '<span style="display:inline-block;min-width:80px;border-bottom:2px dashed var(--kb);color:var(--kb);font-weight:700;padding:0 4px">___________</span>'
                        ),
                      }}
                    />
                  ) : (
                    <p className="text-sm font-semibold leading-snug" style={{ color: "var(--text)" }} dangerouslySetInnerHTML={{ __html: _md(card.front) }} />
                  )}
                  {/* Options */}
                  <div className="flex flex-col gap-2 mt-1">
                    {options.map((opt, oi) => {
                      const isThis = selected === oi;
                      const isRight = oi === card.correct_idx;
                      let borderColor = "var(--border)";
                      let bg = "var(--bg)";
                      let dotBg = "var(--border)";
                      let dotColor = "var(--muted)";
                      if (answered && isRight) { borderColor = "#1a8a5c"; bg = "rgba(26,138,92,0.08)"; dotBg = "#1a8a5c"; dotColor = "#fff"; }
                      else if (answered && isThis && !isRight) { borderColor = "#d4453a"; bg = "rgba(212,69,58,0.07)"; dotBg = "#d4453a"; dotColor = "#fff"; }
                      return (
                        <button key={oi} type="button" onClick={() => select(oi)}
                          disabled={answered}
                          className={`w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors ${!answered ? "active:scale-[0.98] cursor-pointer" : ""}`}
                          style={{ border: `2px solid ${borderColor}`, backgroundColor: bg, color: "var(--text)", opacity: answered && !isThis && !isRight ? 0.45 : 1 }}
                          onMouseEnter={(e) => { if (!answered) { e.currentTarget.style.borderColor = "var(--accent)"; } }}
                          onMouseLeave={(e) => { if (!answered) { e.currentTarget.style.borderColor = borderColor; } }}>
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
                      {isCorrect ? "✓ Richtig!" : <span dangerouslySetInnerHTML={{ __html: `✗ Richtig wäre: ${_md(card.back)}` }} />}
                    </div>
                  )}
                  {/* Source chip + Hint */}
                  <div className="flex items-center justify-between mt-1 gap-2">
                    <div className="min-w-0">
                      {card.source_label && (() => {
                        const ChipIcon = _getChipIcon(card.source_label);
                        return (
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-1 flex-wrap">
                            <button type="button"
                              onClick={() => { if (onSourceClick) onSourceClick(card.source_label!, card.page_number ?? 1, card.start_time, card.back.replace(/[*_#`~<>[\](){}|]/g, "")); }}
                              className="chip-cite inline-flex items-center gap-0.5 text-[10px] font-medium px-2 py-1 rounded-full border-none cursor-pointer transition-colors"
                              style={{ color: "var(--accent)", backgroundColor: "rgba(var(--accent-rgb),0.07)" }}>
                              <ChipIcon size={10} weight="bold" /> {_chunkLabel(card.source_label, card.page_number ?? 1, card.start_time)}
                            </button>
                          </div>
                          <span className="text-[9px] truncate text-[var(--muted)]">{card.source_label}</span>
                        </div>
                        );
                      })()}
                    </div>
                    {tool === "quiz" && !answered && (
                      <button type="button" onClick={requestHint}
                        disabled={hintLoading}
                        className="btn-soft-accent flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full transition-all disabled:opacity-50">
                        <Lightbulb size={13} weight="bold" />
                        {hintLoading ? "Wird geladen…" : "Tipp"}
                      </button>
                    )}
                  </div>
                  {/* Action row: Chat + Weiter */}
                  {answered && (
                    <div className="flex items-center justify-between mt-2">
                      <button type="button" onClick={() => onAskChat(tool === "vokabeltest" || tool === "lueckentext"
                        ? `Erkläre mir den Begriff „${tool === "lueckentext" ? card.back : card.front}" genauer. Was bedeutet er, in welchem Kontext wird er verwendet und welche Zusammenhänge sind wichtig?`
                        : `Erkläre mir folgendes Thema genauer: „${card.front}". Was sind wichtige Details, Beispiele und Zusammenhänge?`)}
                        className="btn-soft-accent flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full transition-all">
                        <Chat size={13} weight="bold" /> Mehr erfahren
                      </button>
                      <button type="button" onClick={advance}
                        className="btn-fill-accent flex items-center gap-1.5 px-5 py-2 rounded-full text-sm font-semibold transition-all">
                        {index >= total - 1 ? "Abschließen" : "Weiter"} <CaretRight size={14} weight="bold" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

