"use client";

/** Heading of a hand-built admin dialog with the same round close button the Modal has. */

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

type Props = {
  children: ReactNode;
  onClose: () => void;
  disabled?: boolean;
};

export default function DialogHeading({ children, onClose, disabled }: Props) {
  const t = useTranslations("common");
  return (
    <div className="flex items-center justify-between gap-4">
      <h2 className="min-w-0 break-words text-lg font-semibold">{children}</h2>
      <button
        type="button"
        onClick={onClose}
        disabled={disabled}
        aria-label={t("close")}
        data-testid="dialog-close"
        className="w-7 h-7 flex-shrink-0 inline-flex items-center justify-center rounded-full btn-icon dark:text-white dark:hover:!text-white transition-colors disabled:opacity-50"
        style={{ backgroundColor: "var(--surface-dim)" }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M18 6 6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
