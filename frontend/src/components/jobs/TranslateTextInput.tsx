"use client";

import { useTranslations } from "next-intl";
import { TRANSLATE_MAX_CHARS } from "@/lib/constants";

interface TranslateTextInputProps {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
}

export default function TranslateTextInput({ value, onChange, disabled = false }: TranslateTextInputProps) {
  const t = useTranslations("tools.translate.textInput");
  const count = value.length;
  const over = count > TRANSLATE_MAX_CHARS;
  const near = count > TRANSLATE_MAX_CHARS * 0.9;

  const counterColor = over
    ? "text-error"
    : near
      ? "text-warning"
      : "text-muted-soft";

  return (
    <div>
      <label htmlFor="translate-text" className="sr-only">{t("label")}</label>
      <textarea
        id="translate-text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={12}
        placeholder={t("placeholder")}
        maxLength={TRANSLATE_MAX_CHARS}
        aria-label={t("label")}
        aria-invalid={over || undefined}
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed resize-y"
      />
      <div className="mt-1 flex justify-end">
        <span className={`text-xs ${counterColor}`}>
          {t("count", {
            count: count.toLocaleString(),
            max: TRANSLATE_MAX_CHARS.toLocaleString(),
          })}
        </span>
      </div>
    </div>
  );
}
