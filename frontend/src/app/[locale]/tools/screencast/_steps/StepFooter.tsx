"use client";

import { useTranslations } from "next-intl";

interface StepFooterProps {
  onBack: (() => void) | null;
  nextLabel: string;
  onNext: () => void;
  nextDisabled?: boolean;
}

/** The same footer for every page where something is decided. */
export default function StepFooter({ onBack, nextLabel, onNext, nextDisabled }: StepFooterProps) {
  const t = useTranslations("tools.screencast");
  return (
    <div className="flex gap-3 mt-10">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-3 text-sm text-foreground-soft border-2 border-border rounded-md hover:border-kb transition-colors"
        >
          {t("common.back")}
        </button>
      )}
      <button
        type="button"
        onClick={onNext}
        disabled={nextDisabled}
        className="flex-1 px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      >
        {nextLabel}
      </button>
    </div>
  );
}
