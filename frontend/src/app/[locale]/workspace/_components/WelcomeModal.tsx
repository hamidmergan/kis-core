"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { readPrefs, updatePrefs } from "@/lib/browserStore";
import Modal from "@/components/ui/Modal";

interface Props {
  /** Missing while auth is still loading, or during an admin impersonation. */
  userId?: number;
  /** Fires once the dialog is out of the way, shown and closed or never due. */
  onSettled?: () => void;
}

/** Shown once per account, right after its very first login. */
export default function WelcomeModal({ userId, onSettled }: Props) {
  const t = useTranslations("welcomeModal");
  const [text, setText] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  // A ref, so a new callback identity does not restart the fetch.
  const settledRef = useRef(onSettled);
  settledRef.current = onSettled;

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    api
      .fetch("/api/health/labels", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled) return;
        const body = data && typeof data.welcome_modal_text === "string" ? data.welcome_modal_text : "";
        if (!data || data.welcome_modal_enabled !== true || !body.trim()) {
          settledRef.current?.();
          return;
        }
        if (readPrefs().welcomeSeen?.includes(userId)) {
          settledRef.current?.();
          return;
        }
        setText(body);
        setOpen(true);
      })
      .catch(() => {
        // The dialog is non-critical, the next one must not wait for it.
        if (!cancelled) settledRef.current?.();
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const handleClose = () => {
    setOpen(false);
    if (!userId) return;
    const seen = readPrefs().welcomeSeen ?? [];
    if (!seen.includes(userId)) updatePrefs({ welcomeSeen: [...seen, userId] });
    settledRef.current?.();
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={t("title")}
      footer={
        <button type="button" onClick={handleClose} className="btn-primary text-sm rounded-lg px-4 py-2">
          {t("cta")}
        </button>
      }
    >
      <p className="text-sm whitespace-pre-line">{text}</p>
    </Modal>
  );
}
