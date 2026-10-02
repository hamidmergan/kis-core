"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";

interface Props {
  title: string;
  text: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  testId?: string;
}

/** Asks before anything that cannot be undone, Cancel has the focus so Enter is safe. */
export default function ConfirmDialog({ title, text, confirmLabel, onConfirm, onCancel, testId }: Props) {
  const tc = useTranslations("eventCommon");
  return (
    <Modal
      open
      onClose={onCancel}
      title={title}
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onCancel} autoFocus className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
            {tc("cancel")}
          </button>
          <button type="button" onClick={onConfirm} className="px-4 py-2 text-sm btn-danger rounded-lg" data-testid={testId}>
            {confirmLabel}
          </button>
        </div>
      }
    >
      <p className="text-sm text-foreground-soft">{text}</p>
    </Modal>
  );
}
