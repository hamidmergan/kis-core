"use client";

import { useTranslations } from "next-intl";
import { type DiagnosisResult } from "./_diagnosis_types";

export function DiagnosisResultScreen({
  result,
  onContinue,
}: {
  result: DiagnosisResult;
  onContinue: () => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining.diagnosis");

  return (
    <div className="flex flex-col items-center gap-6 p-8 max-w-2xl mx-auto w-full">
      <div className="text-center">
        <p className="text-sm uppercase tracking-wider" style={{ color: "var(--muted)" }}>
          {t("resultTitle")}
        </p>
        <p className="mt-2 text-6xl font-bold" style={{ color: "var(--kb)" }}>
          {result.level}
        </p>
      </div>

      <p className="text-center" style={{ color: "var(--foreground)" }}>
        {result.message}
      </p>

      {/* The level is a model estimate, not a certified test result. The note sits
          with the number rather than before the chat, so it qualifies the result
          without making the entry look like an exam. */}
      <p className="text-xs text-center max-w-md" style={{ color: "var(--muted)" }}>
        {t("disclaimer")}
      </p>

      <button
        onClick={onContinue}
        className="mt-2 px-6 py-2 rounded-lg"
        style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}
      >
        {t("continue")}
      </button>
    </div>
  );
}
