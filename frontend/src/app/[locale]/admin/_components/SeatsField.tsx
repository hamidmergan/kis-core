"use client";

/** How often an access code may be redeemed: common sizes in a list, anything else typed in. */

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import { MAX_SEATS, SEATS_CUSTOM, SEAT_PRESETS } from "./seats";

type Props = {
  choice: string;
  custom: string;
  onChoice: (value: string) => void;
  onCustom: (value: string) => void;
};

export default function SeatsField({ choice, custom, onChoice, onCustom }: Props) {
  const t = useTranslations("admin.createAccessCode");

  const options = useMemo(
    () => [
      ...SEAT_PRESETS.map((n) => ({ value: String(n), label: t("seats", { n }) })),
      { value: SEATS_CUSTOM, label: t("customSeats") },
    ],
    [t],
  );

  return (
    <div className="space-y-1">
      <label className="text-xs uppercase tracking-wide text-muted" htmlFor="access-code-seats-choice">
        {t("maxUses")}
      </label>
      <Select
        id="access-code-seats-choice"
        value={choice}
        onChange={onChoice}
        options={options}
        className="w-full"
      />
      {choice === SEATS_CUSTOM && (
        <div className="space-y-1 pt-1">
          <input
            id="access-code-seats"
            data-testid="access-code-seats"
            type="number"
            aria-label={t("customSeats")}
            min={1}
            max={MAX_SEATS}
            step={1}
            required
            value={custom}
            onChange={(e) => onCustom(e.target.value)}
            className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
          <p className="text-xs text-muted-soft">{t("customSeatsHint", { max: MAX_SEATS })}</p>
        </div>
      )}
    </div>
  );
}
