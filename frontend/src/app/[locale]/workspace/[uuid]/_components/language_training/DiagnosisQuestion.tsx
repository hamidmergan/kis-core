"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import type { DiagnosisAnswer, DiagnosisQuestion } from "./_diagnosis_questions";

export function DiagnosisQuestionView({
  question,
  initialAnswer,
  onSubmit,
  onBack,
  showBack,
}: {
  question: DiagnosisQuestion;
  initialAnswer?: DiagnosisAnswer;
  onSubmit: (answer: DiagnosisAnswer) => void;
  onBack: () => void;
  showBack: boolean;
}) {
  const t = useTranslations("workspace.detail.languageTraining.diagnosis");
  const [singleSelected, setSingleSelected] = useState<number | null>(
    initialAnswer?.selectedIndices?.[0] ?? null,
  );
  const [multiSelected, setMultiSelected] = useState<number[]>(
    initialAnswer?.selectedIndices ?? [],
  );
  const [text, setText] = useState<string>(initialAnswer?.text ?? "");

  useEffect(() => {
    setSingleSelected(initialAnswer?.selectedIndices?.[0] ?? null);
    setMultiSelected(initialAnswer?.selectedIndices ?? []);
    setText(initialAnswer?.text ?? "");
  }, [question.id, initialAnswer]);

  const canSubmit = (() => {
    if (question.type === "single") return singleSelected !== null;
    if (question.type === "multi") return multiSelected.length > 0;
    return text.trim().length > 0;
  })();

  function handleSubmit() {
    if (!canSubmit) return;
    if (question.type === "single") {
      onSubmit({ questionId: question.id, selectedIndices: [singleSelected as number] });
    } else if (question.type === "multi") {
      onSubmit({ questionId: question.id, selectedIndices: [...multiSelected].sort((a, b) => a - b) });
    } else {
      onSubmit({ questionId: question.id, text: text.trim() });
    }
  }

  return (
    <div className="flex flex-col gap-4 p-6 max-w-2xl mx-auto w-full">
      <p className="text-base font-medium" style={{ color: "var(--foreground)" }}>
        {question.prompt}
      </p>

      {question.type === "single" && question.options && (
        <div className="flex flex-col gap-2">
          {question.options.map((opt, idx) => {
            const checked = singleSelected === idx;
            return (
              <label
                key={idx}
                className="flex items-center gap-3 p-3 rounded-lg cursor-pointer border transition-colors"
                style={{
                  borderColor: checked ? "var(--kb)" : "var(--border)",
                  backgroundColor: checked ? "var(--kb20)" : "transparent",
                  color: "var(--foreground)",
                }}
              >
                <input
                  type="radio"
                  name={`q-${question.id}`}
                  checked={checked}
                  onChange={() => setSingleSelected(idx)}
                />
                <span>{opt}</span>
              </label>
            );
          })}
        </div>
      )}

      {question.type === "multi" && question.options && (
        <div className="flex flex-col gap-2">
          {question.options.map((opt, idx) => {
            const checked = multiSelected.includes(idx);
            return (
              <label
                key={idx}
                className="flex items-center gap-3 p-3 rounded-lg cursor-pointer border transition-colors"
                style={{
                  borderColor: checked ? "var(--kb)" : "var(--border)",
                  backgroundColor: checked ? "var(--kb20)" : "transparent",
                  color: "var(--foreground)",
                }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => {
                    setMultiSelected((prev) =>
                      e.target.checked ? [...prev, idx] : prev.filter((i) => i !== idx),
                    );
                  }}
                />
                <span>{opt}</span>
              </label>
            );
          })}
        </div>
      )}

      {question.type === "free_text" && (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          className="w-full p-3 rounded-lg border resize-none focus:outline-none focus:ring-2"
          style={{
            borderColor: "var(--border)",
            backgroundColor: "var(--surface)",
            color: "var(--foreground)",
          }}
          placeholder={t("freeTextPlaceholder")}
        />
      )}

      <div className="flex justify-between mt-2">
        <button
          onClick={onBack}
          disabled={!showBack}
          className="px-4 py-2 rounded-lg disabled:opacity-30"
          style={{ color: "var(--muted)" }}
        >
          {t("back")}
        </button>
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="px-5 py-2 rounded-lg disabled:opacity-50"
          style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}
        >
          {t("next")}
        </button>
      </div>
    </div>
  );
}
