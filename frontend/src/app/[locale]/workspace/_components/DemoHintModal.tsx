"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";

interface Props {
  open: boolean;
  /** A join is running, the button waits instead of firing twice. */
  busy: boolean;
  onJoin: () => void;
  onClose: () => void;
}

/** Catches an empty module list, so nobody sits in front of a dead end. */
export default function DemoHintModal({ open, busy, onJoin, onClose }: Props) {
  const t = useTranslations("workspace.demoHint");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("dialogTitle")}
      footer={
        <div className="flex items-center gap-2 w-full">
          <button
            type="button"
            onClick={onClose}
            className="text-sm rounded-lg px-3 py-2 text-foreground-soft border-2 border-border hover:border-kb transition-colors"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            data-testid="demo-hint-join"
            onClick={onJoin}
            disabled={busy}
            className="btn-primary ml-auto text-sm rounded-lg px-4 py-2 disabled:opacity-50"
          >
            {busy ? "…" : t("confirm")}
          </button>
        </div>
      }
    >
      <p className="text-sm" data-testid="demo-hint">{t("dialogBody")}</p>
    </Modal>
  );
}
