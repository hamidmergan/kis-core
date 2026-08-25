"use client";

/**
 * Die Rueckfrage vor dem Loeschen eines Kontos.
 *
 * Baut auf dem Haus-Dialog auf und sieht damit aus wie jede andere Rueckfrage
 * auf der Plattform. Rot ist nur der Knopf, der wirklich loescht.
 */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";

type Vorschau = {
  workspaces: number;
  sources: number;
  messages: number;
  jobs: number;
  enrollments: number;
};

type Props = {
  userId: number;
  userName: string;
  onCancel: () => void;
  onDeleted: () => void;
};

export default function DeleteUserConfirmDialog({
  userId, userName, onCancel, onDeleted,
}: Props) {
  const t = useTranslations("admin.users.delete");
  const [vorschau, setVorschau] = useState<Vorschau | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    fetch(`/api/admin/users/${userId}/deletion-preview`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setVorschau(d));
  }, [userId]);

  const handleConfirm = async () => {
    setSubmitting(true);
    setFehler("");
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setFehler(body?.detail || t("failed"));
        return;
      }
      onDeleted();
    } catch {
      setFehler(t("failed"));
    } finally {
      setSubmitting(false);
    }
  };

  // Nur nennen, was wirklich da ist. Fuenf Nullen lesen sich wie Fuellwerk.
  const posten = vorschau
    ? ([
        ["workspaces", vorschau.workspaces],
        ["sources", vorschau.sources],
        ["messages", vorschau.messages],
        ["jobs", vorschau.jobs],
        ["enrollments", vorschau.enrollments],
      ] as const).filter(([, n]) => n > 0)
    : [];

  return (
    <Modal
      open
      onClose={onCancel}
      title={t("title", { name: userName })}
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
            onClick={handleConfirm}
            disabled={submitting || vorschau === null}
            className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50 flex items-center gap-2"
          >
            {submitting && <Spinner size="xs" color="current" />}
            {t("confirm")}
          </button>
        </div>
      }
    >
      <div className="space-y-3 text-sm text-foreground">
        {vorschau === null ? (
          <p className="flex items-center gap-2 text-muted">
            <Spinner size="xs" /> {t("loading")}
          </p>
        ) : posten.length === 0 ? (
          <p className="text-foreground-soft">{t("nothing")}</p>
        ) : (
          <>
            <p className="text-foreground-soft">{t("intro")}</p>
            <ul className="list-disc pl-5 space-y-1 text-foreground-soft">
              {posten.map(([schluessel, n]) => (
                <li key={schluessel}>{t(schluessel, { n })}</li>
              ))}
            </ul>
            {vorschau.workspaces > 0 && (
              <p className="font-medium">{t("participantsWarning")}</p>
            )}
          </>
        )}
        <p className="text-xs text-muted">{t("warningIrreversible")}</p>
        {fehler && <p className="text-xs text-error">{fehler}</p>}
      </div>
    </Modal>
  );
}
