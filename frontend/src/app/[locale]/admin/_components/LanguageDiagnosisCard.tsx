"use client";

import PromptSettingCard from "./PromptSettingCard";

/** The assessment prompt, a placeholder carries the language. */
export default function LanguageDiagnosisCard() {
  return <PromptSettingCard namespace="admin.languageDiagnosisCard" settingKey="language_diagnosis_prompt" rows={14} />;
}
