"use client";

import { useTranslations } from "next-intl";
import type { DiagnosisResult, Skill } from "./_diagnosis_questions";

const SKILL_ORDER: Skill[] = ["grammar", "vocabulary", "reading", "writing", "pragmatics"];

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
        {result.feedback}
      </p>

      <div className="w-full flex flex-col gap-2 mt-2">
        {SKILL_ORDER.map((skill) => {
          const score = result.skill_scores[skill];
          return (
            <div key={skill} className="flex items-center gap-3">
              <span className="w-28 text-sm" style={{ color: "var(--muted)" }}>
                {t(`skill.${skill}`)}
              </span>
              <div
                className="flex-1 h-2 rounded-full overflow-hidden"
                style={{ backgroundColor: "var(--surface-dim)" }}
              >
                <div
                  className="h-full rounded-full transition-[width]"
                  style={{ width: `${score}%`, backgroundColor: "var(--kb)" }}
                />
              </div>
              <span className="w-10 text-right text-sm tabular-nums" style={{ color: "var(--foreground)" }}>
                {score}
              </span>
            </div>
          );
        })}
      </div>

      <button
        onClick={onContinue}
        className="mt-4 px-6 py-2 rounded-lg"
        style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}
      >
        {t("continue")}
      </button>
    </div>
  );
}
