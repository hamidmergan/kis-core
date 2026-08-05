"use client";

/**
 * Reiter "Einstufung": ob eingestuft wird und was der Test abfragt.
 *
 * Der Nachbarreiter "KI-Verhalten" traegt die vier grossen Textfelder. Wer nur
 * den Sprachtrainer einschalten will, soll nicht durch Prompts scrollen müssen.
 */

import { useTranslations } from "next-intl";
import DiagnosisQuestionPlanCard from "../../_components/DiagnosisQuestionPlanCard";
import { useSetting } from "../../_settings/SettingsProvider";
import { SettingCard, ToggleSetting } from "../../_settings/fields";

export default function LanguageLevelPage() {
  const tTrainer = useTranslations("admin.languageTrainerCard");
  const tLang = useTranslations("admin.diagnosisLanguage");
  const trainer = useSetting<boolean>("language_training_enabled", false);

  return (
    <div className="space-y-4">
      <ToggleSetting
        field={trainer}
        title={tTrainer("title")}
        activeText={tTrainer("active")}
        disabledText={tTrainer("disabled")}
        hint={tTrainer("description")}
        label={tTrainer("toggleAria")}
      />

      {/* Die Sprache ist noch nicht wählbar, das Feld steht hier, damit sichtbar
          bleibt worauf sich der Test bezieht. */}
      <SettingCard
        title={tLang("label")}
        description={tLang("hint")}
        control={
          <select
            value="de"
            disabled
            aria-label={tLang("label")}
            className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <option value="de">{tLang("german")}</option>
          </select>
        }
      />

      <DiagnosisQuestionPlanCard />
    </div>
  );
}
