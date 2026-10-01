"use client";

import { useTranslations } from "next-intl";

interface StepFooterProps {
  onBack: (() => void) | null;
  nextLabel: string;
  onNext: () => void;
  nextDisabled?: boolean;
}

/** The same footer for every page where something is decided, pinned to the bottom on the phone. */
export default function StepFooter({ onBack, nextLabel, onNext, nextDisabled }: StepFooterProps) {
  const t = useTranslations("tools.screencast");
  return (
    // On the phone the footer stays in reach while scrolling and stops at the end of the step.
    <div className="flex gap-3 mt-10 sticky bottom-0 z-30 -mx-4 px-4 py-3 border-t border-border-soft bg-background sm:static sm:mx-0 sm:px-0 sm:py-0 sm:border-0 sm:bg-transparent">
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
