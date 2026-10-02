"use client";

/** Small form pieces shared by the station and tile editors. */

import { useTranslations } from "next-intl";
import { ICON_KEYS, EVENT_ICONS } from "@/lib/event/icons";
import type { IconKey, Text2 } from "@/lib/event/types";

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
  const t = useTranslations("eventCommon");
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

/** All icons as tiles at once, no names shown, the name stays as tooltip and screen reader text. */
export function IconSelect({
  value,
  onChange,
  label,
}: {
  value: IconKey;
  onChange: (next: IconKey) => void;
  label: string;
}) {
  const t = useTranslations("eventIcons");
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <span className="text-xs text-muted">{label}</span>
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
        {ICON_KEYS.map((key) => {
          const Icon = EVENT_ICONS[key];
          const selected = key === value;
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={t(key)}
              title={t(key)}
              onClick={() => onChange(key)}
              className={`w-10 h-10 flex items-center justify-center rounded-lg border-2 transition-colors hover:border-kb ${
                selected ? "border-kb text-kb bg-kb/5" : "border-border text-foreground-soft"
              }`}
            >
              <Icon size={20} weight="bold" aria-hidden="true" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
