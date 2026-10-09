"use client";

import { useLocale, useTranslations } from "next-intl";

/** The text field of a text source with its character count, over the limit it turns red. */
export function TextSourceArea({
  value,
  onChange,
  maxChars,
  disabled,
  rows = 8,
  error,
  testId,
}: {
  value: string;
  onChange: (value: string) => void;
  maxChars: number;
  disabled?: boolean;
  rows?: number;
  error?: boolean;
  testId?: string;
}) {
  const t = useTranslations("workspace.detail.sources");
  const locale = useLocale();
  const count = value.trim().length;
  const over = count > maxChars;
  const fmt = new Intl.NumberFormat(locale);
  return (
    <div>
      <textarea
        value={value}
        disabled={disabled}
        rows={rows}
        placeholder={t("textPlaceholder")}
        aria-label={t("textHeading")}
        data-testid={testId}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full rounded-lg border-2 px-3 py-2 text-sm focus:outline-none resize-y transition-colors ${
          error || over ? "border-error-border" : "border-border focus:border-kb"
        }`}
        style={{ backgroundColor: "var(--background)", color: "var(--foreground)" }}
      />
      <p className="text-xs mt-1 text-right" style={{ color: over ? "var(--error)" : "var(--muted)" }}>
        {t("textCount", { count: fmt.format(count), max: fmt.format(maxChars) })}
      </p>
    </div>
  );
}
