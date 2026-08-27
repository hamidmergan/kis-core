"use client";

/** The confirmation before an account loses the demo flag. */

import { useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";

type Props = {
  /** Name of the account that loses the flag. */
  verlierer: string;
  /** True when switching to another account. */
  wechsel: boolean;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
};

export default function DemoConfirmDialog({ verlierer, wechsel, onCancel, onConfirm }: Props) {
  const t = useTranslations("admin.users.demoConfirm");
  const [submitting, setSubmitting] = useState(false);

  const bestaetigen = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open
      onClose={onCancel}
      title={wechsel ? t("titleSwitch") : t("titleRemove")}
      size="sm"
      closeOnBackdropClick={!submitting}
      closeOnEscape={!submitting}
      footer={
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="btn-cancel px-4 py-2 text-sm border border-border rounded-lg text-foreground-soft transition-colors disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            data-testid="demo-confirm"
            onClick={bestaetigen}
            disabled={submitting}
            className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50 flex items-center gap-2"
          >
            {submitting && <Spinner size="xs" color="current" />}
            {t("confirm")}
          </button>
        </div>
      }
    >
      <div className="space-y-3 text-sm text-foreground">
        <p className="text-foreground-soft">
          {wechsel ? t("bodySwitch", { old: verlierer }) : t("bodyRemove", { name: verlierer })}
        </p>
        <p className="text-xs text-muted">{t("keeps")}</p>
      </div>
    </Modal>
  );
}
