"use client";

/** Creates a reset link for one account, the old password stays until the person sets a new one. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy, Warning } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import { copyTextFromPromise } from "@/lib/clipboard";
import { resetUrl } from "./resetUrl";

type Props = {
  userId: number;
  userName: string;
  onClose: () => void;
};

export default function ResetLinkDialog({ userId, userName, onClose }: Props) {
  const t = useTranslations("admin.users.resetLink");
  const [link, setLink] = useState<{ token: string; expires_at: string } | null>(null);
  const [fehler, setFehler] = useState("");
  const [kopiert, setKopiert] = useState(false);

  useEffect(() => {
    let abgebrochen = false;
    (async () => {
      try {
        const r = await fetch(`/api/admin/users/${userId}/reset-link`, {
          method: "POST",
          credentials: "include",
        });
        const body = await r.json().catch(() => null);
        if (abgebrochen) return;
        if (r.ok) setLink(body);
        else setFehler(typeof body?.detail === "string" ? body.detail : t("failed"));
      } catch {
        if (!abgebrochen) setFehler(t("failed"));
      }
    })();
    return () => {
      abgebrochen = true;
    };
  }, [userId, t]);

  const url = link ? resetUrl(window.location.origin, link.token) : "";

  function copy() {
    copyTextFromPromise(Promise.resolve(url));
    setKopiert(true);
    setTimeout(() => setKopiert(false), 1500);
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t("title", { name: userName })}
      size="sm"
      footer={
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="btn-cancel px-4 py-2 text-sm border border-border rounded-lg text-foreground-soft transition-colors"
          >
            {t("close")}
          </button>
        </div>
      }
    >
      <div className="space-y-3 text-sm">
        {fehler ? (
          <p className="text-error-strong">{fehler}</p>
        ) : !link ? (
          <Spinner className="flex justify-center py-4" />
        ) : (
          <>
            <div className="space-y-1">
              <span className="text-xs uppercase tracking-wide text-muted">{t("linkLabel")}</span>
              <div className="flex items-center gap-2">
                <code className="flex-1 min-w-0 truncate font-mono text-sm bg-surface border border-border rounded-md px-3 py-2 select-all">
                  {url}
                </code>
                <button
                  type="button"
                  onClick={copy}
                  className="px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap"
                >
                  {kopiert ? <Check size={16} weight="bold" /> : <Copy size={16} weight="bold" />}
                  {kopiert ? t("copied") : t("copy")}
                </button>
              </div>
            </div>
            <div className="flex items-start gap-2 bg-warn-bg text-warn-strong rounded-md px-3 py-2">
              <Warning size={18} weight="bold" className="mt-0.5 shrink-0" />
              <span>
                {t("warning", {
                  date: new Date(link.expires_at).toLocaleDateString("de-DE", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  }),
                })}
              </span>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
