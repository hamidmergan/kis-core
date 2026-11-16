"use client";

/** Create an access code: the form first, then the code to copy. */

import { useState } from "react";
import { useTranslations } from "next-intl";
import CopyTextButton from "./CopyTextButton";
import { hoursToChoice } from "./accessHours";
import AccessCodeQr from "./AccessCodeQr";
import { AccessCodeFlags, AccessCodeLimits, useAccessCodeForm } from "./AccessCodeForm";
import CodeWorkspacesField from "./CodeWorkspacesField";
import DialogHeading from "./DialogHeading";

type Props = {
  onClose: () => void;
  onCreated: () => void;
};

type Erstellt = { code: string; label: string };

export default function CreateAccessCodeDialog({ onClose, onCreated }: Props) {
  const t = useTranslations("admin.createAccessCode");
  const tWs = useTranslations("admin.codeWorkspaces");
  const form = useAccessCodeForm({
    label: "",
    role: "staff",
    seats: { choice: "10", custom: "" },
    days: { choice: "7", custom: "" },
    hours: hoursToChoice(168),
    showCredentials: true,
    showEvaluation: false,
    workspaceIds: [],
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [erstellt, setErstellt] = useState<Erstellt | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.payload) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch("/api/admin/access-codes", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form.payload),
      });
      if (r.ok) {
        const resp = await r.json();
        setErstellt({ code: resp.code, label: resp.label });
        onCreated();
      } else {
        const body = await r.json().catch(() => ({}));
        setError(typeof body?.detail === "string" ? body.detail : t("errorGeneric"));
      }
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border border-border rounded-xl shadow-xl w-full max-w-md max-h-[90dvh] overflow-y-auto p-6 space-y-4">
        {erstellt ? (
          <>
            <DialogHeading onClose={onClose}>{t("createdTitle")}</DialogHeading>
            <p className="text-sm text-muted-soft">{t("createdHint")}</p>

            <div className="flex items-center gap-2">
              <code
                data-testid="access-code-value"
                className="flex-1 min-w-0 truncate font-mono text-lg bg-surface border border-border rounded-md px-3 py-2 select-all"
              >
                {erstellt.code}
              </code>
              <CopyTextButton text={() => erstellt.code} copyLabel={t("copy")} copiedLabel={t("copied")} />
            </div>

            <AccessCodeQr code={erstellt.code} label={erstellt.label} />

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm btn-primary rounded-md transition-colors"
              >
                {t("close")}
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <DialogHeading onClose={onClose} disabled={submitting}>{t("title")}</DialogHeading>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted" htmlFor="access-code-label">
                {t("label")}
              </label>
              <input
                id="access-code-label"
                type="text"
                required
                autoFocus
                value={form.label}
                onChange={(e) => form.setLabel(e.target.value)}
                className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
              />
              <p className="text-xs text-muted-soft">{t("labelHint")}</p>
            </div>

            <AccessCodeLimits form={form} />

            <CodeWorkspacesField value={form.workspaceIds} onChange={form.setWorkspaceIds} hint={tWs("hintCreate")} />

            <AccessCodeFlags form={form} />

            {error && <p className="text-sm text-error">{error}</p>}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
              >
                {t("cancel")}
              </button>
              <button
                type="submit"
                data-testid="access-code-submit"
                disabled={submitting || !form.canSubmit}
                className="px-4 py-2 text-sm btn-primary rounded-md transition-colors disabled:opacity-60"
              >
                {submitting ? t("submitting") : t("submit")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
