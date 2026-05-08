"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Copy, Check, Warning } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";

type EmployeeType = "staff" | "student";

type Props = {
  onClose: () => void;
};

type FormState = {
  uid: string;
  given_name: string;
  surname: string;
  email: string;
  employee_type: EmployeeType;
};

const EMPTY: FormState = {
  uid: "",
  given_name: "",
  surname: "",
  email: "",
  employee_type: "staff",
};

export default function CreateLdapUserDialog({ onClose }: Props) {
  const t = useTranslations("admin.createLdapUser");
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ uid: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const employeeTypeOptions = [
    { value: "staff", label: t("employeeTypeStaff") },
    { value: "student", label: t("employeeTypeStudent") },
  ];

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch("/api/admin/ldap-users", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (r.ok) {
        const body = await r.json();
        setSuccess({ uid: body.uid, password: body.generated_password });
      } else {
        const body = await r.json().catch(() => ({}));
        setError(body.detail || t("errorGeneric"));
      }
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSubmitting(false);
    }
  }

  async function copyPassword() {
    if (!success) return;
    await navigator.clipboard.writeText(success.password);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-background border border-border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        {success ? (
          <>
            <h2 className="text-lg font-semibold">{t("successTitle")}</h2>
            <p className="text-sm text-muted-soft">uid: <span className="font-mono">{success.uid}</span></p>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("successPasswordLabel")}</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 font-mono text-sm bg-surface border border-border rounded-md px-3 py-2 select-all">
                  {success.password}
                </code>
                <button
                  type="button"
                  onClick={copyPassword}
                  className="px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1"
                >
                  {copied ? <Check size={16} weight="bold" /> : <Copy size={16} weight="bold" />}
                  {copied ? t("successCopied") : t("successCopyButton")}
                </button>
              </div>
            </div>

            <div className="flex items-start gap-2 bg-warning-bg text-warning-strong text-sm rounded-md px-3 py-2">
              <Warning size={18} weight="bold" className="mt-0.5 shrink-0" />
              <span>{t("successWarning")}</span>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm bg-kb text-white rounded-md"
              >
                {t("successClose")}
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <h2 className="text-lg font-semibold">{t("title")}</h2>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("fieldUid")}</label>
              <input
                type="text"
                required
                value={form.uid}
                onChange={(e) => update("uid", e.target.value.toLowerCase())}
                pattern="[a-z0-9_.-]{2,32}"
                className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb font-mono"
              />
              <p className="text-xs text-muted-soft">{t("fieldUidHint")}</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wide text-muted">{t("fieldGivenName")}</label>
                <input
                  type="text"
                  required
                  value={form.given_name}
                  onChange={(e) => update("given_name", e.target.value)}
                  className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs uppercase tracking-wide text-muted">{t("fieldSurname")}</label>
                <input
                  type="text"
                  required
                  value={form.surname}
                  onChange={(e) => update("surname", e.target.value)}
                  className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("fieldEmail")}</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("fieldEmployeeType")}</label>
              <Select
                value={form.employee_type}
                onChange={(v) => update("employee_type", v as EmployeeType)}
                options={employeeTypeOptions}
                className="w-full"
              />
            </div>

            {error && (
              <p className="text-sm text-error">{error}</p>
            )}

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
                disabled={submitting}
                className="px-4 py-2 text-sm bg-kb text-white rounded-md disabled:opacity-60"
              >
                {t("submit")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
