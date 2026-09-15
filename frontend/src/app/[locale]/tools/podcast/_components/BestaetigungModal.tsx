"use client";

/** The question before a click throws away the script or stops the voicing. */

import Modal from "@/components/ui/Modal";

interface BestaetigungModalProps {
  title: string;
  body: string;
  /** Label of the harmless way out. */
  dismissLabel: string;
  confirmLabel: string;
  onDismiss: () => void;
  onConfirm: () => void;
}

export default function BestaetigungModal(props: BestaetigungModalProps) {
  const { title, body, dismissLabel, confirmLabel, onDismiss, onConfirm } = props;

  return (
    <Modal
      open
      onClose={onDismiss}
      title={title}
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onDismiss}
            className="btn-cancel px-4 py-2 text-sm border border-border rounded-lg text-foreground-soft transition-colors"
          >
            {dismissLabel}
          </button>
          <button
            type="button"
            data-testid="podcast-bestaetigen"
            onClick={onConfirm}
            className="px-4 py-2 text-sm btn-danger rounded-lg"
          >
            {confirmLabel}
          </button>
        </div>
      }
    >
      <p className="text-sm text-foreground-soft">{body}</p>
    </Modal>
  );
}
