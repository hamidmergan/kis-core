"use client";

/** Small form pieces shared by the station and tile editors. */

import { useTranslations } from "next-intl";
import Select from "@/components/ui/Select";
import { ICON_KEYS, MOCKUP_ICONS } from "../../../_lib/icons";
import type { IconKey, Text2 } from "../../../_lib/types";

export const INPUT =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:border-kb disabled:opacity-50";

export const BTN_PRIMARY = "px-3 py-2 text-sm btn-primary rounded-md transition-colors whitespace-nowrap";
export const BTN_SECONDARY =
  "px-4 py-2 text-sm rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-60";

export function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 min-w-0">
      <span className="text-xs text-muted">{label}</span>
      {children}
    </label>
  );
}

/** One label, two inputs: German and English side by side where there is room. */
export function TextPair({
  label,
  value,
  onChange,
  rows,
}: {
  label: string;
  value: Text2;
  onChange: (next: Text2) => void;
  rows?: number;
}) {
  const t = useTranslations("mockup.common");
  const field = (lang: "de" | "en") =>
    rows ? (
      <textarea
        value={value[lang]}
        rows={rows}
        onChange={(e) => onChange({ ...value, [lang]: e.target.value })}
        aria-label={`${label} ${t(lang)}`}
        className={`${INPUT} resize-y`}
      />
    ) : (
      <input
        type="text"
        value={value[lang]}
        onChange={(e) => onChange({ ...value, [lang]: e.target.value })}
        aria-label={`${label} ${t(lang)}`}
        className={INPUT}
      />
    );
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <span className="text-xs text-muted">{label}</span>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <span className="text-2xs text-muted-soft">{t("de")}</span>
          {field("de")}
        </div>
        <div className="flex flex-col gap-1 min-w-0">
          <span className="text-2xs text-muted-soft">{t("en")}</span>
          {field("en")}
        </div>
      </div>
    </div>
  );
}

export function IconSelect({
  value,
  onChange,
  label,
}: {
  value: IconKey;
  onChange: (next: IconKey) => void;
  label: string;
}) {
  const t = useTranslations("mockup.icons");
  const options = ICON_KEYS.map((key) => {
    const Icon = MOCKUP_ICONS[key];
    return {
      value: key,
      label: (
        <span className="inline-flex items-center gap-2">
          <Icon size={16} weight="bold" aria-hidden="true" />
          {t(key)}
        </span>
      ),
    };
  });
  return (
    <Labeled label={label}>
      <Select<IconKey> value={value} onChange={onChange} options={options} ariaLabel={label} />
    </Labeled>
  );
}
