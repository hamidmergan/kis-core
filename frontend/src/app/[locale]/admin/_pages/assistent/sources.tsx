"use client";

/**
 * Quellen des KI-Assistenten: was hochgeladen werden darf und wie es eingelesen
 * wird. Alles hier betrifft nur den Assistenten, nicht die globalen Tools.
 *
 * Vorher lagen diese fünf Karten verstreut in einer Liste von siebzehn unter
 * "System", zwischen Wartungsmodus und Maskottchen.
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
      <ReindexCard />
    </div>
  );
}
