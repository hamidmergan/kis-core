"use client";

/**
 * Quellen des KI-Assistenten: was hochgeladen werden darf, wie es eingelesen
 * wird und wie viel davon in eine Anfrage geht. Alles hier betrifft nur den
 * Assistenten, nicht die globalen Tools.
 *
 * Vorher lagen diese Karten verstreut in einer Liste von siebzehn unter
 * "System", zwischen Wartungsmodus und Maskottchen.
 *
 * Hier standen einmal zwei Zahlenfelder für die Kontext-Budgets von Chat und
 * Werkzeugen. Sie sind am 14.08.2026 entfallen. Eine Zahl von Hand konnte gar
 * nicht für alle Modelle stimmen, die Fenster reichen von 20.080 bis 1.048.576
 * Token, und ein zu grosses Budget hiess HTTP 400 statt einer Antwort. Was ein
 * Modell verträgt, wird jetzt einmal gemessen und daraus gerechnet.
 */

import { useTranslations } from "next-intl";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { useSetting } from "../../_settings/SettingsProvider";
import { NumberSetting, ToggleSetting } from "../../_settings/fields";
import ReindexCard from "../../_settings/ReindexCard";

export default function SourcesPage() {
  const labels = useWorkspaceLabel();
  const tLimits = useTranslations("admin.workspaceLimitsCard");
  const tPages = useTranslations("admin.sourceMaxPagesCard");
  const tOcr = useTranslations("admin.ocrCard");

  const maxSources = useSetting<number>("aia_workspace_max_sources", 50);
  const maxPages = useSetting<number>("aia_source_max_pages", 100);
  const ocr = useSetting<boolean>("ocr_enabled", true);

  return (
    <div className="space-y-4">
      <NumberSetting
        field={maxSources}
        title={tLimits("title", { label: labels.singular })}
        hint={tLimits("hint", { label: labels.singular })}
        unit={tLimits("unit")}
        min={1}
        max={1000}
        outOfRange={tLimits("outOfRange")}
      />
      <NumberSetting
        field={maxPages}
        title={tPages("title")}
        hint={tPages("hint")}
        unit={tPages("unit")}
        min={1}
        max={2000}
        outOfRange={tPages("outOfRange")}
      />
      <ToggleSetting
        field={ocr}
        title={tOcr("title")}
        activeText={tOcr("active")}
        disabledText={tOcr("disabled")}
        hint={tOcr("hint")}
        label={tOcr("toggleAria")}
      />
      {/* Die zwei Kontextbudgets standen hier bis zum 14.08.2026 als Zahlenfelder.
          Sie sind entfallen: wie viel Kontext ein Modell vertraegt, wird jetzt einmal
          gemessen und daraus gerechnet. Der gemessene Wert steht im KI-Bereich neben
          dem Modell. */}
      {/* Ganz unten, weil das als einziges hier ein Knopf ist und nicht eine
          Einstellung. Man liest die Regeln von oben nach unten und handelt am
          Ende, nicht mittendrin. */}
      <ReindexCard />
    </div>
  );
}
