"use client";

/** How long an access code stays redeemable: presets in a list, anything else typed in. */

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import { MAX_VALID_DAYS, VALID_DAYS_CUSTOM, VALID_DAYS_PRESETS } from "./validDays";

type Props = {
  choice: string;
  custom: string;
  onChoice: (value: string) => void;
  onCustom: (value: string) => void;
};

export default function ValidDaysField({ choice, custom, onChoice, onCustom }: Props) {
  const t = useTranslations("admin.createAccessCode");

  const options = useMemo(
    () => [
      ...VALID_DAYS_PRESETS.map((n) => ({ value: String(n), label: t("days", { n }) })),
      { value: VALID_DAYS_CUSTOM, label: t("customDays") },
    ],
    [t],
  );

  return (
    <div className="space-y-1">
      <label className="text-xs uppercase tracking-wide text-muted" htmlFor="access-code-days-choice">
        {t("validDays")}
      </label>
      <Select
        id="access-code-days-choice"
        value={choice}
        onChange={onChoice}
        options={options}
        className="w-full"
      />
      {choice === VALID_DAYS_CUSTOM && (
        <div className="space-y-1 pt-1">
          <input
            id="access-code-days"
            data-testid="access-code-days"
            type="number"
            aria-label={t("customDays")}
            min={1}
            max={MAX_VALID_DAYS}
            step={1}
            required
            value={custom}
            onChange={(e) => onCustom(e.target.value)}
            className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
          <p className="text-xs text-muted-soft">{t("customDaysHint", { max: MAX_VALID_DAYS })}</p>
        </div>
      )}
    </div>
  );
}
