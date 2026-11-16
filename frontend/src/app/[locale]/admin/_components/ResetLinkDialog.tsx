"use client";

/** Creates a reset link for one account, the old password stays until the person sets a new one. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Warning } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import CopyTextButton from "./CopyTextButton";
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
                <CopyTextButton text={() => url} copyLabel={t("copy")} copiedLabel={t("copied")} />
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
