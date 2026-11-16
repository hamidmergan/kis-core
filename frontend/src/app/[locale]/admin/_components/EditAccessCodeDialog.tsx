"use client";

/** Edit an access code: everything but the code itself. */

import { useState } from "react";
import { useTranslations } from "next-intl";
import { seatsToChoice } from "./seats";
import { hoursToChoice } from "./accessHours";
import { AccessCodeFlags, AccessCodeLimits, useAccessCodeForm } from "./AccessCodeForm";
import CodeWorkspacesField from "./CodeWorkspacesField";
import DialogHeading from "./DialogHeading";
import { daysToChoice, remainingDays } from "./validDays";

type Code = {
  id: number;
  code: string;
  label: string;
  role: string;
  custom_role_id: number | null;
  max_uses: number;
  used_count: number;
  valid_until: string;
  access_hours: number | null;
  show_credentials: boolean;
  show_evaluation: boolean;
  workspaces: { id: number; title: string; owner_id: number | null }[];
};

type Props = {
  code: Code;
  onClose: () => void;
  onSaved: () => void;
};

export default function EditAccessCodeDialog({ code, onClose, onSaved }: Props) {
  const t = useTranslations("admin.editAccessCode");
  const tCreate = useTranslations("admin.createAccessCode");
  const tWs = useTranslations("admin.codeWorkspaces");
  const form = useAccessCodeForm({
    label: code.label,
    role: code.custom_role_id ? `custom:${code.custom_role_id}` : code.role,
    seats: seatsToChoice(code.max_uses),
    days: daysToChoice(remainingDays(code.valid_until)),
    hours: hoursToChoice(code.access_hours),
    showCredentials: code.show_credentials,
    showEvaluation: code.show_evaluation,
    workspaceIds: code.workspaces.map((w) => w.id),
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.payload) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch(`/api/admin/access-codes/${code.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form.payload),
      });
      if (r.ok) {
        onSaved();
        onClose();
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
        <form onSubmit={submit} className="space-y-3">
          <DialogHeading onClose={onClose} disabled={submitting}>{t("title")}</DialogHeading>

          <div className="space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted">{t("code")}</span>
            <p className="font-mono text-sm text-foreground-soft">{code.code}</p>
          </div>

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted" htmlFor="edit-access-code-label">
              {tCreate("label")}
            </label>
            <input
              id="edit-access-code-label"
              type="text"
              required
              autoFocus
              value={form.label}
              onChange={(e) => form.setLabel(e.target.value)}
              className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
            />
          </div>

          <AccessCodeLimits form={form} />

          <CodeWorkspacesField value={form.workspaceIds} onChange={form.setWorkspaceIds} initial={code.workspaces} hint={tWs("hintEdit")} />

          <AccessCodeFlags form={form} />

          {error && <p className="text-sm text-error">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
            >
              {tCreate("cancel")}
            </button>
            <button
              type="submit"
              data-testid="access-code-edit-submit"
              disabled={submitting || !form.canSubmit}
              className="px-4 py-2 text-sm btn-primary rounded-md transition-colors disabled:opacity-60"
            >
              {submitting ? t("submitting") : t("submit")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
