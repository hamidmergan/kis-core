"use client";

/** How much may come in, grouped by who the limit applies to. */

import { useTranslations } from "next-intl";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { useSetting } from "../../_settings/SettingsProvider";
import { NumberSetting } from "../../_settings/fields";
import Block from "./_block";

/** The value the two count limits carry for unlimited. */
const UNBEGRENZT = -1;

export default function GrenzenMaterialPage() {
  const t = useTranslations("admin.grenzen");
  const tLimits = useTranslations("admin.workspaceLimitsCard");
  const tPages = useTranslations("admin.sourceMaxPagesCard");
  const tTool = useTranslations("admin.toolLimits");
  const labels = useWorkspaceLabel();

  const maxSources = useSetting<number>("aia_workspace_max_sources", 50);
  const maxPages = useSetting<number>("aia_source_max_pages", 200);
  const upload = useSetting<number>("upload_max_mb", 500);
  const minutes = useSetting<number>("transcription_max_minutes", 100);
  const slides = useSetting<number>("screencast_max_slides", 50);
  const kept = useSetting<number>("results_kept_per_user", 100);
  const open = useSetting<number>("tool_max_open_jobs", 5);

  return (
    <div className="space-y-8">
      <Block title={t("werkzeuge")}>
        <NumberSetting
          field={slides}
          title={tTool("slides.title")}
          hint={tTool("slides.hint")}
          unit={tTool("slides.unit")}
          min={1}
          max={200}
          outOfRange={tTool("slides.outOfRange")}
        />
        {/* min ist -1, nicht 1: die Prüfung im Baustein würde ein Unbegrenzt sonst
            zurückweisen, bevor es das Backend überhaupt sieht. */}
        <NumberSetting
          field={open}
          title={tTool("open.title")}
          hint={tTool("open.hint")}
          unit={tTool("open.unit")}
          min={UNBEGRENZT}
          max={100}
          outOfRange={tTool("open.outOfRange")}
        />
        <NumberSetting
          field={kept}
          title={tTool("kept.title")}
          hint={tTool("kept.hint")}
          unit={tTool("kept.unit")}
          min={UNBEGRENZT}
          max={10000}
          outOfRange={tTool("kept.outOfRange")}
        />
      </Block>

      <Block title={t("assistent")}>
        <NumberSetting
          field={maxSources}
          title={tLimits("title", { label: labels.singular })}
          hint={tLimits("hint", { label: labels.singular })}
          unit={tLimits("unit")}
          min={1}
          max={1000}
          outOfRange={tLimits("outOfRange")}
        />
      </Block>

      <Block title={t("gemeinsam")}>
        <NumberSetting
          field={upload}
          title={tTool("upload.title")}
          hint={tTool("upload.hint")}
          unit={tTool("upload.unit")}
          min={10}
          max={2000}
          outOfRange={tTool("upload.outOfRange")}
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
        <NumberSetting
          field={minutes}
          title={tTool("minutes.title")}
          hint={tTool("minutes.hint")}
          unit={tTool("minutes.unit")}
          min={5}
          max={480}
          outOfRange={tTool("minutes.outOfRange")}
        />
      </Block>
    </div>
  );
}
