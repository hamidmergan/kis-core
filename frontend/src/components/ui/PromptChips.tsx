"use client";

import { useTranslations } from "next-intl";

interface PromptChipsProps {
  onChipClick: (chip: string) => void;
  disabled?: boolean;
  chips: string[];
  ariaLabelKey?: string;
}

export default function PromptChips({ onChipClick, disabled, chips, ariaLabelKey }: PromptChipsProps) {
  const t = useTranslations("common");
  const ariaLabel = ariaLabelKey ?? t("pleaseSelect");
  return (
    <div className="flex flex-wrap gap-2 mt-3" aria-label={ariaLabel}>
      {chips.map((chip) => (
        <button
          key={chip}
          type="button"
          onClick={() => onChipClick(chip)}
          disabled={disabled}
          className="px-3 py-1 text-xs rounded-full border border-kb text-kb hover:bg-[var(--kb20)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb"
        >
          {chip}
        </button>
      ))}
    </div>
  );
}
