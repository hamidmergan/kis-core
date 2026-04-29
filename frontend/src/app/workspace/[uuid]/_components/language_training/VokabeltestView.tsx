import { useState } from "react";
import { CaretRight, Exam } from "@phosphor-icons/react";
import type { VocabTestQuestion } from "../../_types";
import { SubviewHeader, type BreadcrumbItem } from "../layout/SubviewHeader";

export function VokabeltestView({
  questions, loading, onGenerate, onBack, breadcrumbs,
}: {
  questions: VocabTestQuestion[]; loading: boolean;
  onGenerate: () => void; onBack: () => void;
  breadcrumbs?: BreadcrumbItem[];
}) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [current, setCurrent] = useState(0);
  const [finished, setFinished] = useState(false);

  const total = questions.length;
  const q = questions[current];

  function handleSelect(optIdx: number) {
    if (answers[current] !== undefined) return;
    setAnswers({ ...answers, [current]: optIdx });
  }

  function handleAdvance() {
    if (current + 1 < total) {
      setCurrent(current + 1);
    } else {
      setFinished(true);
      const finalAnswers = { ...answers };
    }
  }

  const correctCount = Object.entries(answers).filter(
    ([i, optIdx]) => questions[Number(i)]?.correct_index === optIdx
  ).length;

  if (finished) {
    return (
      <div className="flex flex-col h-full">
        <SubviewHeader title="Begriffe-Quiz" toolKey="TermQuiz" onBack={onBack} breadcrumbs={breadcrumbs} category="language_training" />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full px-4 pt-8 pb-6 flex flex-col items-center gap-5" style={{ maxWidth: 560 }}>
            <div className="text-center">
              <p className="text-lg font-bold" style={{ color: "var(--foreground)" }}>Ergebnis</p>
              <p className="text-3xl font-bold mt-2" style={{ color: "var(--kb)" }}>
                {correctCount} / {total}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                {Math.round((correctCount / total) * 100)}% richtig
              </p>
            </div>
            <div className="w-full rounded-full h-2.5 overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
              <div className="h-full rounded-full" style={{ width: `${(correctCount / total) * 100}%`, backgroundColor: "#22c55e" }} />
            </div>
            <div className="flex gap-2 w-full">
              <button type="button"
                onClick={() => { setCurrent(0); setAnswers({}); setFinished(false); onGenerate(); }}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-white transition-opacity hover:opacity-90"
                style={{ backgroundColor: "var(--kb)" }}
              >
                Neuer Test
              </button>
              <button type="button" onClick={onBack}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: "var(--border)", color: "var(--foreground)" }}
              >
                Zurück
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title="Begriffe-Quiz" toolKey="TermQuiz" onBack={onBack} breadcrumbs={breadcrumbs} category="language_training" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-4 pt-4 pb-6 flex flex-col gap-4" style={{ maxWidth: 560 }}>
          <button
            type="button"
            onClick={() => { onGenerate(); setCurrent(0); setAnswers({}); setFinished(false); }}
            disabled={loading}
            className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-opacity hover:opacity-90"
            style={{ backgroundColor: "var(--kb)" }}
          >
            <span className="flex items-center justify-center gap-2">
              <Exam size={16} weight="bold" />
              {loading ? "Generiere…" : "Begriffe-Quiz starten"}
            </span>
          </button>

          {q && !loading && (
            <>
              <div className="text-center text-xs font-semibold" style={{ color: "var(--muted)" }}>
                {current + 1} / {total}
              </div>

              <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
                <p className="text-sm font-semibold mb-4 leading-snug" style={{ color: "var(--foreground)" }}>
                  {q.question}
                </p>
                <div className="flex flex-col gap-2">
                  {q.options.map((opt, oi) => {
                    const answered = answers[current] !== undefined;
                    const isCorrect = oi === q.correct_index;
                    const isSelected = answers[current] === oi;
                    let bg = "var(--background)";
                    let border = "var(--border)";
                    let color = "var(--foreground)";
                    if (answered) {
                      if (isCorrect) { bg = "var(--success-bg)"; border = "var(--success-border)"; color = "var(--success-strong)"; }
                      else if (isSelected && !isCorrect) { bg = "var(--error-bg)"; border = "var(--error-border)"; color = "var(--error-strong)"; }
                    }
                    return (
                      <button
                        key={oi}
                        type="button"
                        onClick={() => handleSelect(oi)}
                        disabled={answered}
                        className="w-full text-left px-3 py-2.5 rounded-lg text-sm font-semibold disabled:cursor-default transition-colors"
                        style={{ backgroundColor: bg, border: `1px solid ${border}`, color }}
                      >
                        {["A", "B", "C", "D"][oi]}. {opt}
                      </button>
                    );
                  })}
                </div>
                {answers[current] !== undefined && (
                  <button type="button" onClick={handleAdvance}
                    className="mt-2 self-end flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90"
                    style={{ backgroundColor: "var(--kb)" }}>
                    {current + 1 >= total ? "Abschließen" : "Weiter"} <CaretRight size={12} weight="bold" />
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

