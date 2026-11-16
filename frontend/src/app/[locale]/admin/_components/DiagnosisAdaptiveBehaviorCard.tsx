"use client";

import PromptSettingCard from "./PromptSettingCard";

/** The adaptive answer behaviour of the chat, empty resets to the default. */
export default function DiagnosisAdaptiveBehaviorCard() {
  return <PromptSettingCard namespace="admin.adaptiveBehaviorCard" settingKey="language_diagnosis_adaptive_behavior" rows={8} />;
}
