"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";

import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";

interface ExitConfirmModalProps {
  mode: "cancel" | "restart" | "render";
  onCancel: () => void;
  onConfirm: () => void;
}

// Cancelling the render deletes nothing, hence its own texts instead of the discard warning.
const TEXTE = {
  cancel: { titel: "exit.cancelTitle", text: "exit.body", warnung: "exit.warning", ja: "exit.confirm", nein: "common.cancel" },
  restart: { titel: "exit.restartTitle", text: "exit.body", warnung: "exit.warning", ja: "exit.confirm", nein: "common.cancel" },
  render: { titel: "exit.renderTitle", text: "exit.renderBody", warnung: "exit.renderWarning", ja: "exit.renderConfirm", nein: "exit.renderKeep" },
} as const;

export default function ExitConfirmModal({ mode, onCancel, onConfirm }: ExitConfirmModalProps) {
  const t = useTranslations("tools.screencast");
  const texte = TEXTE[mode];
  const press = useRef(newBackdropPress()).current;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
      {...backdropClose(press, onCancel)}
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold mb-2">{t(texte.titel)}</h3>
        <p className="text-sm text-foreground-soft mb-1">{t(texte.text)}</p>
        <p className="text-sm text-error mb-6">{t(texte.warnung)}</p>
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={onCancel}
            autoFocus
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
          >
            {t(texte.nein)}
          </button>
          <button type="button" onClick={onConfirm} className="px-4 py-2 text-sm btn-danger rounded-lg">
            {t(texte.ja)}
          </button>
        </div>
      </div>
    </div>
  );
}
