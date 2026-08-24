"use client";

/**
 * Grenzen der globalen Werkzeuge: wie groß und wie viel angenommen wird.
 *
 * Die Auswahl folgt einer einzigen Frage: hängt der richtige Wert von der
 * Nutzung der Hochschule ab oder von der Technik? Nur das Erste steht hier.
 * Alles Gemessene bleibt fest im Code, die Begründung je Wert steht in
 * ``backend/src/services/tool_limits.py``.
 */

import { useTranslations } from "next-intl";
import { useSetting } from "../../_settings/SettingsProvider";
import { NumberSetting } from "../../_settings/fields";

/** Der Wert, den die beiden Zaehlgrenzen fuer "unbegrenzt" tragen. */
const UNBEGRENZT = -1;

export default function ToolLimitsPage() {
  const t = useTranslations("admin.toolLimits");

  const slides = useSetting<number>("screencast_max_slides", 50);
  const minutes = useSetting<number>("transcription_max_minutes", 100);
  const upload = useSetting<number>("upload_max_mb", 500);
  const kept = useSetting<number>("results_kept_per_user", 100);
  const open = useSetting<number>("screencast_max_open_jobs", 5);

  return (
    <div className="space-y-4">
      <NumberSetting
        field={slides}
        title={t("slides.title")}
        hint={t("slides.hint")}
        unit={t("slides.unit")}
        min={1}
        max={200}
        outOfRange={t("slides.outOfRange")}
      />
      <NumberSetting
        field={minutes}
        title={t("minutes.title")}
        hint={t("minutes.hint")}
        unit={t("minutes.unit")}
        min={5}
        max={480}
        outOfRange={t("minutes.outOfRange")}
      />
      <NumberSetting
        field={upload}
        title={t("upload.title")}
        hint={t("upload.hint")}
        unit={t("upload.unit")}
        min={10}
        max={2000}
        outOfRange={t("upload.outOfRange")}
      />
      {/* min ist -1, nicht 1: die Prüfung im Baustein würde ein Unbegrenzt sonst
          zurückweisen, bevor es das Backend überhaupt sieht. */}
      <NumberSetting
        field={kept}
        title={t("kept.title")}
        hint={t("kept.hint")}
        unit={t("kept.unit")}
        min={UNBEGRENZT}
        max={10000}
        outOfRange={t("kept.outOfRange")}
      />
      <NumberSetting
        field={open}
        title={t("open.title")}
        hint={t("open.hint")}
        unit={t("open.unit")}
        min={UNBEGRENZT}
        max={100}
        outOfRange={t("open.outOfRange")}
      />
    </div>
  );
}
