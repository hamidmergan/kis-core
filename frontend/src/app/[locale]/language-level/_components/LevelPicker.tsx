"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import StatusMark from "@/components/ui/StatusMark";
import { CEFR_LEVELS, type CefrLevel } from "@/lib/cefr";

/** The six steps as a list to pick from, the medallion above previews the choice. */
export function LevelPicker({
  own,
  selected,
  busy,
  onSelect,
  onApply,
  onCancel,
  onTest,
}: {
  own: CefrLevel | null;
  selected: CefrLevel | null;
  busy: boolean;
  onSelect: (level: CefrLevel) => void;
  onApply: () => void;
  onCancel: () => void;
  onTest: () => void;
}) {
  const t = useTranslations("languageLevel.languageTraining");
  const [hovered, setHovered] = useState<CefrLevel | null>(null);

  return (
    <div className="flex w-full flex-col items-center gap-8">
      <div role="radiogroup" aria-label={t("chooseSelf")} className="flex w-full flex-col gap-2">
        {CEFR_LEVELS.map((step) => {
          const isSelected = step === selected;
          let borderColor = "var(--border)";
          const bg = isSelected ? "var(--surface)" : "var(--background)";
          if (isSelected) borderColor = "var(--kb)";
          else if (hovered === step) borderColor = "var(--kb)";
          return (
            <button
              key={step}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => onSelect(step)}
              onMouseEnter={() => setHovered(step)}
              onMouseLeave={() => setHovered((h) => (h === step ? null : h))}
              className="w-full text-left flex items-start gap-3 px-4 py-3 rounded-xl text-sm border-2 transition-colors cursor-pointer"
              style={{ borderColor, backgroundColor: bg, color: "var(--foreground)" }}
            >
              <span
                className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                style={{
                  backgroundColor: isSelected ? "var(--kb)" : "var(--border)",
                  color: isSelected ? "var(--on-accent)" : "var(--muted)",
                }}
              >
                {step}
              </span>
              <span className="flex flex-col gap-1">
                <span className="flex items-center gap-2">
                  <span className="font-medium">{t(`levels.${step}.name`)}</span>
                  {step === own && (
                    <StatusMark tone="brand" className="text-xs">{t("current")}</StatusMark>
                  )}
                </span>
                <span style={{ color: "var(--muted)" }}>{t(`levels.${step}.long`)}</span>
              </span>
            </button>
          );
        })}
      </div>
      <div className="flex flex-col items-center gap-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onApply}
            disabled={busy || !selected || selected === own}
            className="px-4 py-2 text-sm btn-primary rounded-lg disabled:opacity-50"
          >
            {t("apply")}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50"
          >
            {t("cancel")}
          </button>
        </div>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          {t("ratherTest")}{" "}
          <button type="button" onClick={onTest} className="underline font-medium hover:opacity-80 transition-opacity">
            {t("takeTest")}
          </button>
        </p>
      </div>
    </div>
  );
}
