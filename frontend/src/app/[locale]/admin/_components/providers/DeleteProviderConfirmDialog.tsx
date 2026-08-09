"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Warning } from "@phosphor-icons/react";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";
import type { Feature } from "./_types";

type Props = {
  providerName: string;
  affectedFeatures: Feature[];
  onCancel: () => void;
  onConfirm: () => Promise<void> | void;
};

export default function DeleteProviderConfirmDialog({
  providerName, affectedFeatures, onCancel, onConfirm,
}: Props) {
  const t = useTranslations("admin.providers.delete");
  const tFeature = useTranslations("admin.providers.featureName");
  const [submitting, setSubmitting] = useState(false);
  const press = useRef(newBackdropPress()).current;

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

  const hasRoutes = affectedFeatures.length > 0;
  const featureList = affectedFeatures.map((f) => tFeature(f)).join(", ");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" {...backdropClose(press, handleBackdropClick)}>
      <div className="bg-background border border-red-300 dark:border-red-700 rounded-xl shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="p-5 bg-red-50 dark:bg-red-950/30 border-b border-red-200 dark:border-red-800 rounded-t-xl flex items-start gap-3">
          <Warning size={22} weight="fill" className="text-red-600 dark:text-red-400 shrink-0" />
          <h2 className="text-base font-semibold text-red-700 dark:text-red-300">
            {t("title", { name: providerName })}
          </h2>
        </div>

        <div className="p-5 space-y-3 text-sm text-foreground">
          <p className="whitespace-pre-line">
            {hasRoutes
              ? t("bodyWithRoutes", { name: providerName, features: featureList })
              : t("bodyEmpty", { name: providerName })}
          </p>
          {hasRoutes && (
            <p className="text-amber-700 dark:text-amber-400 flex gap-2">
              <Warning size={14} weight="bold" className="shrink-0 mt-0.5" />
              <span>{t("warningFeaturesUnavailable")}</span>
            </p>
          )}
          <p className="text-muted text-xs">{t("warningIrreversible")}</p>
        </div>

        <div className="p-5 border-t border-border-soft flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            autoFocus
            className="px-3 py-1.5 text-sm font-medium border border-border-soft rounded-md hover:bg-surface"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting}
            className="px-3 py-1.5 text-sm font-medium bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
          >
            {t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
