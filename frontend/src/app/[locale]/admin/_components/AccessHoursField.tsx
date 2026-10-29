"use client";

/** How long an account made from an access code stays alive: presets in a list, anything else typed in. */

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import { ACCESS_HOURS_CUSTOM, ACCESS_HOURS_PRESETS, ACCESS_HOURS_UNLIMITED, MAX_ACCESS_HOURS } from "./accessHours";

type Props = {
  choice: string;
  custom: string;
  onChoice: (value: string) => void;
  onCustom: (value: string) => void;
};

/** 12 hours stays in hours, 24 and more shows as whole days. */
function presetLabel(hours: number, t: ReturnType<typeof useTranslations>): string {
  return hours % 24 === 0 ? t("days", { n: hours / 24 }) : t("hours", { n: hours });
}

export default function AccessHoursField({ choice, custom, onChoice, onCustom }: Props) {
  const t = useTranslations("admin.createAccessCode");

  const options = useMemo(
    () => [
      ...ACCESS_HOURS_PRESETS.map((n) => ({ value: String(n), label: presetLabel(n, t) })),
      { value: ACCESS_HOURS_CUSTOM, label: t("customHours") },
      { value: ACCESS_HOURS_UNLIMITED, label: t("unlimited") },
    ],
    [t],
  );

  return (
    <div className="space-y-1">
      <label className="text-xs uppercase tracking-wide text-muted" htmlFor="access-code-hours-choice">
        {t("accessHours")}
      </label>
      <Select
        id="access-code-hours-choice"
        value={choice}
        onChange={onChoice}
        options={options}
        className="w-full"
      />
      {choice === ACCESS_HOURS_CUSTOM && (
        <div className="space-y-1 pt-1">
          <input
            id="access-code-hours"
            data-testid="access-code-hours"
            type="number"
            aria-label={t("customHours")}
            min={1}
            max={MAX_ACCESS_HOURS}
            step={1}
            required
            value={custom}
            onChange={(e) => onCustom(e.target.value)}
            className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
          <p className="text-xs text-muted-soft">{t("customHoursHint", { max: MAX_ACCESS_HOURS })}</p>
        </div>
      )}
    </div>
  );
}
