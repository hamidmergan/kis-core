"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { CaretRight } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import type { FeatureProvider } from "@/hooks/useFeatureProviders";

interface Option<T extends string> {
  key: T;
  label: string;
}

/** One row of choices, exactly one is active, on the tinted band the free ones keep a white ground. */
export function Chips<T extends string>({ label, optionen, wert, onChange, disabled }: {
  label: string;
  optionen: ReadonlyArray<Option<T>>;
  wert: T;
  onChange: (wert: T) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={label}>
      {optionen.map((o) => (
        <button
          key={o.key}
          type="button"
          role="radio"
          aria-checked={wert === o.key}
          disabled={disabled}
          onClick={() => onChange(o.key)}
          className={`px-3 py-1.5 text-xs font-medium rounded-md border-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
            wert === o.key
              ? "border-kb bg-kb/10 text-kb dark:text-foreground"
              : "border-border bg-background text-foreground-soft hover:border-kb"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Label on the left, choices on the right, so the eye runs down one column of labels. */
export function Reihe({ label, hinweis, children }: { label: string; hinweis?: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[5.25rem_minmax(0,1fr)] gap-3 py-3">
      <p className="text-sm font-medium text-foreground-soft pt-1.5">{label}</p>
      <div className="min-w-0">
        {children}
        {hinweis && <p className="mt-1.5 text-xs text-muted">{hinweis}</p>}
      </div>
    </div>
  );
}

/** The provider row, with at most one provider there is nothing to choose and the row stays away. */
export function AnbieterReihe({ providers, value, onChange, disabled }: {
  providers: FeatureProvider[];
  value: number | null;
  onChange: (id: number) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("tools.image");
  if (providers.length <= 1) return null;
  return (
    <Reihe label={t("providerLabel")}>
      <Select
        value={String(value ?? "")}
        onChange={(v) => onChange(Number(v))}
        disabled={disabled}
        ariaLabel={t("providerLabel")}
        options={providers.map((p) => ({ value: String(p.id), label: p.name }))}
      />
    </Reihe>
  );
}

/** The tinted settings band, it folds away and then names in one line what is set. */
export function Band({ offen, onToggle, zusammenfassung, children }: {
  offen: boolean;
  onToggle: () => void;
  zusammenfassung: string;
  children: ReactNode;
}) {
  const t = useTranslations("tools.image.settings");
  return (
    <div className="mt-4 rounded-xl bg-kb/5">
      <button type="button" onClick={onToggle} aria-expanded={offen}
        className="w-full text-left flex items-start gap-2 px-4 py-3.5 rounded-xl">
        <CaretRight size={12} weight="bold"
          className={`mt-1 flex-shrink-0 text-muted-soft transition-transform ${offen ? "rotate-90" : ""}`} />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-foreground">{t("title")}</span>
          {!offen && <span className="block text-xs text-muted mt-0.5">{zusammenfassung}</span>}
        </span>
        <span className="text-xs text-muted-soft mt-0.5">{offen ? t("hide") : t("show")}</span>
      </button>
      <div className={offen ? "px-4 pb-2 divide-y divide-kb/10" : "hidden"}>{children}</div>
    </div>
  );
}
