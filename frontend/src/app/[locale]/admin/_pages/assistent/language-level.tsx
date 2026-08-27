"use client";

/** Whether an assessment happens and what the test asks. */

import { useTranslations } from "next-intl";
import DiagnosisQuestionPlanCard from "../../_components/DiagnosisQuestionPlanCard";
import { useSetting } from "../../_settings/SettingsProvider";
import { ToggleSetting } from "../../_settings/fields";

export default function LanguageLevelPage() {
  const tTrainer = useTranslations("admin.languageTrainerCard");
  const trainer = useSetting<boolean>("language_training_enabled", false);

  // A locked dropdown with one option looked like a setting.
  return (
    <div className="space-y-4">
      <ToggleSetting
        field={trainer}
        title={tTrainer("title")}
        disabledText={tTrainer("disabled")}
        hint={tTrainer("description")}
        label={tTrainer("toggleAria")}
      />

      <DiagnosisQuestionPlanCard />
    </div>
  );
}
