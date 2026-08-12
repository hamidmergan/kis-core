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
import { ToggleSetting } from "../../_settings/fields";

export default function LanguageLevelPage() {
  const tTrainer = useTranslations("admin.languageTrainerCard");
  const trainer = useSetting<boolean>("language_training_enabled", false);

  // Eine gesperrte Auswahl mit genau einer Option sah nach Einstellung aus, war
  // aber keine: der Test ist deutsch. Der Hinweis darauf steht jetzt in der Karte
  // Fragen-Plan, wo man ihn beim Schreiben der Fragen auch braucht.
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

      <DiagnosisQuestionPlanCard />
    </div>
  );
}
