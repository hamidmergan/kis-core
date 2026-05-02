import { useState } from "react";
import { CaretRight, Check, TextAa, XIcon } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import type { ClozeExercise } from "../../_types";
import { SubviewHeader, type BreadcrumbItem } from "../layout/SubviewHeader";

export function LueckentextView({
  exercises, loading, onGenerate, onBack, breadcrumbs,
}: {
  exercises: ClozeExercise[]; loading: boolean;
  onGenerate: () => void; onBack: () => void;
  breadcrumbs?: BreadcrumbItem[];
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [finished, setFinished] = useState(false);

  const total = exercises.length;
  const ex = exercises[current];

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
    ([i, optIdx]) => exercises[Number(i)]?.options[optIdx] === exercises[Number(i)]?.answer
  ).length;

  if (finished) {
    return (
      <div className="flex flex-col h-full">
        <SubviewHeader title={t("tools.lueckentext")} toolKey="Cloze" onBack={onBack} breadcrumbs={breadcrumbs} category="language_training" />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full px-4 pt-8 pb-6 flex flex-col items-center gap-5" style={{ maxWidth: 560 }}>
            <div className="text-center">
              <p className="text-lg font-bold" style={{ color: "var(--foreground)" }}>{t("common.result")}</p>
              <p className="text-3xl font-bold mt-2" style={{ color: "var(--kb)" }}>
                {correctCount} / {total}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                {t("lueckentext.percentCorrect", { pct: Math.round((correctCount / total) * 100) })}
              </p>
            </div>
            <div className="w-full rounded-full h-2.5 overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
              <div className="h-full rounded-full" style={{ width: `${(correctCount / total) * 100}%`, backgroundColor: "#22c55e" }} />
            </div>
            <div className="flex gap-2 w-full">
              <button
                type="button"
                onClick={() => { setCurrent(0); setAnswers({}); setFinished(false); onGenerate(); }}
                className="btn-primary flex-1 py-2.5 rounded-xl text-xs font-semibold"
              >
                {t("lueckentext.newExercise")}
              </button>
              <button type="button" onClick={onBack}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-colors hover:bg-[var(--surface-dim)]"
                style={{ backgroundColor: "var(--border)", color: "var(--foreground)" }}
              >
                {t("common.back")}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title={t("tools.lueckentext")} toolKey="Cloze" onBack={onBack} breadcrumbs={breadcrumbs} category="language_training" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-4 pt-4 pb-6 flex flex-col gap-4" style={{ maxWidth: 560 }}>
          <button
            type="button"
            onClick={() => { onGenerate(); setCurrent(0); setAnswers({}); setFinished(false); }}
            disabled={loading}
            className="btn-primary w-full py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50"
          >
            <span className="flex items-center justify-center gap-2">
              <TextAa size={16} weight="bold" />
              {loading ? t("lueckentext.generating") : t("lueckentext.startButton")}
            </span>
          </button>

          {ex && !loading && (
            <>
              <div className="text-center text-xs font-semibold" style={{ color: "var(--muted)" }}>
                {current + 1} / {total}
              </div>

              <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
                <p className="text-sm leading-relaxed font-semibold mb-4" style={{ color: "var(--foreground)" }}>
                  {ex.sentence}
                </p>
                <div className="flex flex-col gap-2">
                  {ex.options.map((opt, oi) => {
                    const answered = answers[current] !== undefined;
                    const isCorrect = opt === ex.answer;
                    const isSelected = answers[current] === oi;
                    let bg = "var(--background)";
                    let border = "var(--border)";
                    let color = "var(--foreground)";
                    if (answered) {
                      if (isCorrect) { bg = "var(--success-bg)"; border = "var(--success-border)"; color = "var(--success-strong)"; }
                      else if (isSelected) { bg = "var(--error-bg)"; border = "var(--error-border)"; color = "var(--error-strong)"; }
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
                  <p className="flex items-center gap-1 text-xs mt-3 font-semibold"
                    style={{ color: ex.options[answers[current]] === ex.answer ? "var(--success-strong)" : "var(--error-strong)" }}
                  >
                    {ex.options[answers[current]] === ex.answer
                      ? <><Check size={12} weight="bold" /> {t("lueckentext.answerCorrect")}</>
                      : <><XIcon size={12} weight="bold" /> {t("lueckentext.answerCorrectIs", { answer: ex.answer })}</>}
                  </p>
                )}
                {answers[current] !== undefined && (
                  <button type="button" onClick={handleAdvance}
                    className="btn-primary mt-2 self-end flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold">
                    {current + 1 >= total ? t("common.finish") : t("common.next")} <CaretRight size={12} weight="bold" />
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
