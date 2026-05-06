"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { GraduationCap, X, ArrowClockwise } from "@phosphor-icons/react";
import { useLanguageDiagnosis } from "../../_hooks/useLanguageDiagnosis";
import { DiagnosisQuestionView } from "./DiagnosisQuestion";
import { DiagnosisResultScreen } from "./DiagnosisResultScreen";

interface Props {
  userId: number | null;
  onComplete: () => void;
  onAbort: () => void;
  hideHeader?: boolean;
}

export function LanguageDiagnosisPanel({ userId, onComplete, onAbort, hideHeader }: Props) {
  const t = useTranslations("workspace.detail.languageTraining.diagnosis");
  const [confirmAbort, setConfirmAbort] = useState(false);

  const {
    questions,
    answers,
    currentIndex,
    status,
    result,
    errorMessage,
    submitAnswer,
    goBack,
    submit,
    retry,
  } = useLanguageDiagnosis(userId);

  const allAnswered = answers.length === questions.length;
  const currentQuestion = questions[currentIndex];
  const initialAnswerForCurrent = answers.find((a) => a.questionId === currentQuestion.id);

  return (
    <div className="flex flex-col h-full">
      {!hideHeader && (
        <div
          className="flex items-center justify-between px-4 py-3 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center gap-2">
            <GraduationCap weight="bold" size={20} style={{ color: "var(--kb)" }} />
            <span className="font-semibold" style={{ color: "var(--foreground)" }}>
              {t("title")}
            </span>
            {status === "answering" && (
              <span className="text-sm ml-2" style={{ color: "var(--muted)" }}>
                {t("progress", { current: currentIndex + 1, total: questions.length })}
              </span>
            )}
          </div>
          <button
            onClick={() => setConfirmAbort(true)}
            className="p-1 rounded hover:bg-[var(--surface-dim)]"
            style={{ color: "var(--muted)" }}
            aria-label={t("abort")}
          >
            <X weight="bold" size={18} />
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {status === "answering" && !allAnswered && (
          <DiagnosisQuestionView
            key={currentQuestion.id}
            question={currentQuestion}
            initialAnswer={initialAnswerForCurrent}
            onSubmit={submitAnswer}
            onBack={goBack}
            showBack={currentIndex > 0}
          />
        )}

        {status === "answering" && allAnswered && (
          <div className="flex flex-col items-center gap-4 p-8 max-w-2xl mx-auto w-full">
            <p style={{ color: "var(--foreground)" }}>{t("readyToSubmit")}</p>
            <button
              onClick={submit}
              className="px-6 py-2 rounded-lg"
              style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}
            >
              {t("submit")}
            </button>
            <button onClick={goBack} className="text-sm" style={{ color: "var(--muted)" }}>
              {t("back")}
            </button>
          </div>
        )}

        {status === "submitting" && (
          <div className="flex flex-col items-center gap-3 p-12">
            <ArrowClockwise weight="bold" size={32} className="animate-spin" style={{ color: "var(--kb)" }} />
            <p style={{ color: "var(--foreground)" }}>{t("loading")}</p>
          </div>
        )}

        {status === "error" && (
          <div className="flex flex-col items-center gap-4 p-8">
            <p style={{ color: "var(--error)" }}>{errorMessage || t("errorGeneric")}</p>
            <button
              onClick={retry}
              className="px-5 py-2 rounded-lg"
              style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}
            >
              {t("retry")}
            </button>
          </div>
        )}

        {status === "done" && result && (
          <DiagnosisResultScreen result={result} onContinue={onComplete} />
        )}
      </div>

      {confirmAbort && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setConfirmAbort(false)}
        >
          <div
            className="rounded-2xl p-6 max-w-sm w-full mx-4"
            style={{ backgroundColor: "var(--surface)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="font-semibold mb-2" style={{ color: "var(--foreground)" }}>
              {t("abortConfirmTitle")}
            </p>
            <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>
              {t("abortConfirmBody")}
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmAbort(false)}
                className="px-4 py-2 rounded-lg"
                style={{ color: "var(--foreground)" }}
              >
                {t("abortConfirmKeep")}
              </button>
              <button
                onClick={() => {
                  setConfirmAbort(false);
                  onAbort();
                }}
                className="px-4 py-2 rounded-lg"
                style={{ backgroundColor: "var(--error)", color: "var(--on-accent)" }}
              >
                {t("abortConfirmDiscard")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
