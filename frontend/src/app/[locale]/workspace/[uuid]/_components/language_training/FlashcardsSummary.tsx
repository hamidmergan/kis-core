import { Check, Question } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";

/** The closing screen of a flashcard round, vocabulary counts terms, cards count verdicts. */
export function FlashcardsResults({ isVocab, total, results, onAgain, onDone }: {
  isVocab: boolean;
  total: number;
  results: Record<number, boolean>;
  onAgain: () => void;
  onDone: () => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const verdicts = Object.values(results);
  const correctCount = verdicts.filter(Boolean).length;
  const wrongCount = verdicts.length - correctCount;
  const pendingCount = total - verdicts.length;
  const pct = total > 0 ? Math.round((correctCount / total) * 100) : 0;
  return (
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
      ) : (
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
      )}
      <div className="flex gap-3 mt-4">
        <button type="button" onClick={onAgain}
          className="btn-outline-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
          {t("common.again")}
        </button>
        <button type="button" onClick={onDone}
          className="btn-fill-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
          {t("common.done")}
        </button>
      </div>
    </div>
  );
}

/** Asked at the end when cards were skipped: look at them or finish anyway. */
export function PendingPrompt({ pendingCount, onViewPending, onFinish }: {
  pendingCount: number;
  onViewPending: () => void;
  onFinish: () => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
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
        <button type="button" onClick={onViewPending}
          className="btn-fill-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
          {t("flashcardsLearn.viewPending")}
        </button>
        <button type="button" onClick={onFinish}
          className="btn-outline-accent px-5 py-2 rounded-full text-xs font-semibold transition-all">
          {t("flashcardsLearn.finishAnyway")}
        </button>
      </div>
    </div>
  );
}
