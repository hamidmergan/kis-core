"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { readPrefs, updatePrefs } from "@/lib/browserStore";
import Modal from "@/components/ui/Modal";

interface Props {
  /** Missing while auth is still loading, or during an admin impersonation. */
  userId?: number;
}

/** Shown once per account, right after its very first login. */
export default function WelcomeModal({ userId }: Props) {
  const t = useTranslations("welcomeModal");
  const [text, setText] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    api
      .fetch("/api/health/labels", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled) return;
        const body = data && typeof data.welcome_modal_text === "string" ? data.welcome_modal_text : "";
        if (!data || data.welcome_modal_enabled !== true || !body.trim()) return;
        if (readPrefs().welcomeSeen?.includes(userId)) return;
        setText(body);
        setOpen(true);
      })
      .catch(() => { /* the dialog is non-critical */ });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const handleClose = () => {
    setOpen(false);
    if (!userId) return;
    const seen = readPrefs().welcomeSeen ?? [];
    if (!seen.includes(userId)) updatePrefs({ welcomeSeen: [...seen, userId] });
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
