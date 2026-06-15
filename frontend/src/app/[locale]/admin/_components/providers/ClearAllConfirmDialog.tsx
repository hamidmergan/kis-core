"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";

type Props = {
  providerCount: number;
  routeCount: number;
  onCancel: () => void;
  onConfirm: () => Promise<void> | void;
};

export default function ClearAllConfirmDialog({
  providerCount, routeCount, onCancel, onConfirm,
}: Props) {
  const t = useTranslations("admin.providers.clearAll");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, submitting]);

  const handleBackdropClick = () => {
    if (!submitting) onCancel();
  };

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={handleBackdropClick}>
      <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold mb-2">{t("title")}</h3>
        <p className="text-sm text-foreground-soft mb-1 whitespace-pre-line">
          {t("bodyCounts", { providers: providerCount, routes: routeCount })}
        </p>
        <p className="text-sm text-error mb-1">{t("warningFeaturesUnavailable")}</p>
        <p className="text-sm text-foreground-soft mb-6">{t("warningIrreversible")}</p>
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={onCancel}
            autoFocus
            disabled={submitting}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting}
            className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50"
          >
            {t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
