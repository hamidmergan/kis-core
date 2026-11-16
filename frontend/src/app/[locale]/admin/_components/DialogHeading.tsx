"use client";

/** Heading of a hand-built admin dialog with the same round close button the Modal has. */

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import CloseIcon from "@/components/ui/CloseIcon";

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
        <CloseIcon />
      </button>
    </div>
  );
}
