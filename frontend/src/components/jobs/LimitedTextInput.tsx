"use client";

import { useTranslations } from "next-intl";

interface LimitedTextInputProps {
  /** Where label, placeholder and counter text come from. */
  namespace: "tools.translate.textInput" | "tools.tts.textInput";
  id: string;
  maxChars: number;
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
}

/** A text field with a character counter that warns near the limit. */
export default function LimitedTextInput({ namespace, id, maxChars, value, onChange, disabled = false }: LimitedTextInputProps) {
  const t = useTranslations(namespace);
  const count = value.length;
  const over = count > maxChars;
  const near = count > maxChars * 0.9;

  const counterColor = over
    ? "text-error"
    : near
      ? "text-warning"
      : "text-muted-soft";

  return (
    <div>
      <label htmlFor={id} className="sr-only">{t("label")}</label>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={12}
        placeholder={t("placeholder")}
        maxLength={maxChars}
        aria-label={t("label")}
        aria-invalid={over || undefined}
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed resize-y"
      />
      <div className="mt-1 flex justify-end">
        <span className={`text-xs ${counterColor}`}>
          {t("count", {
            count: count.toLocaleString(),
            max: maxChars.toLocaleString(),
          })}
        </span>
      </div>
    </div>
  );
}
