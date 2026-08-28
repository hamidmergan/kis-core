"use client";

/** Create an access code: the form first, then the code to copy. */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Copy, Check } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import { copyTextFromPromise } from "@/lib/clipboard";

type Props = {
  onClose: () => void;
  onCreated: () => void;
};

type CustomRole = { id: number; name: string };

type Erstellt = { code: string; label: string };

const MAX_USES = [10, 25, 50, 100];
const VALID_DAYS = [7, 14, 30, 60];
const ACCESS_DAYS = [7, 14, 21, 30];

export default function CreateAccessCodeDialog({ onClose, onCreated }: Props) {
  const t = useTranslations("admin.createAccessCode");
  const [label, setLabel] = useState("");
  const [role, setRole] = useState("staff");
  const [maxUses, setMaxUses] = useState("10");
  const [validDays, setValidDays] = useState("7");
  const [accessDays, setAccessDays] = useState("7");
  const [customRoles, setCustomRoles] = useState<CustomRole[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [erstellt, setErstellt] = useState<Erstellt | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch("/api/admin/roles", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.custom_roles) setCustomRoles(d.custom_roles);
      })
      .catch(() => {});
  }, []);

  const roleOptions = useMemo(
    () => [
      { value: "staff", label: t("roleStaff") },
      { value: "user", label: t("roleUser") },
      ...customRoles.map((r) => ({ value: `custom:${r.id}`, label: r.name })),
    ],
    [t, customRoles],
  );

  const maxUsesOptions = useMemo(
    () => MAX_USES.map((n) => ({ value: String(n), label: t("seats", { n }) })),
    [t],
  );

  const validDaysOptions = useMemo(
    () => VALID_DAYS.map((n) => ({ value: String(n), label: t("days", { n }) })),
    [t],
  );

  const accessDaysOptions = useMemo(
    () => [
      ...ACCESS_DAYS.map((n) => ({ value: String(n), label: t("days", { n }) })),
      { value: "0", label: t("unlimited") },
    ],
    [t],
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const custom = role.startsWith("custom:");
    try {
      const r = await fetch("/api/admin/access-codes", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: label.trim(),
          max_uses: Number(maxUses),
          valid_days: Number(validDays),
          access_days: accessDays === "0" ? null : Number(accessDays),
          kis_role: custom ? "custom" : role,
          custom_role_id: custom ? Number(role.slice("custom:".length)) : null,
        }),
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

  function copyCode() {
    if (!erstellt) return;
    copyTextFromPromise(Promise.resolve(erstellt.code));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border border-border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        {erstellt ? (
          <>
            <h2 className="text-lg font-semibold">{t("createdTitle")}</h2>
            <p className="text-sm text-muted-soft">{t("createdHint")}</p>

            <div className="flex items-center gap-2">
              <code
                data-testid="access-code-value"
                className="flex-1 min-w-0 truncate font-mono text-lg bg-surface border border-border rounded-md px-3 py-2 select-all"
              >
                {erstellt.code}
              </code>
              <button
                type="button"
                onClick={copyCode}
                className="px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap"
              >
                {copied ? <Check size={16} weight="bold" /> : <Copy size={16} weight="bold" />}
                {copied ? t("copied") : t("copy")}
              </button>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm bg-kb text-white rounded-md"
              >
                {t("close")}
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <h2 className="text-lg font-semibold">{t("title")}</h2>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted" htmlFor="access-code-label">
                {t("label")}
              </label>
              <input
                id="access-code-label"
                type="text"
                required
                autoFocus
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
              />
              <p className="text-xs text-muted-soft">{t("labelHint")}</p>
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("maxUses")}</label>
              <Select value={maxUses} onChange={setMaxUses} options={maxUsesOptions} className="w-full" />
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("validDays")}</label>
              <Select value={validDays} onChange={setValidDays} options={validDaysOptions} className="w-full" />
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("accessDays")}</label>
              <Select value={accessDays} onChange={setAccessDays} options={accessDaysOptions} className="w-full" />
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("role")}</label>
              <Select value={role} onChange={setRole} options={roleOptions} className="w-full" />
            </div>

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
                disabled={submitting || !label.trim()}
                className="px-4 py-2 text-sm bg-kb text-white rounded-md disabled:opacity-60"
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
