"use client";

/** Create an invitation: the form first, then the link to copy. */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Copy, Check, Warning } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import { copyTextFromPromise } from "@/lib/clipboard";
import { inviteUrl } from "./inviteUrl";
import { uidPreview } from "./uidPreview";

type Props = {
  onClose: () => void;
  onCreated: () => void;
};

type CustomRole = { id: number; name: string };

type Erstellt = { token: string; uid: string; expires_at: string };

const TAGE = [7, 14, 30];

export default function CreateInviteDialog({ onClose, onCreated }: Props) {
  const t = useTranslations("admin.createInvite");
  const [username, setUsername] = useState("");
  const [role, setRole] = useState("staff");
  const [days, setDays] = useState("7");
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

  const dayOptions = useMemo(
    () => TAGE.map((n) => ({ value: String(n), label: t("days", { n }) })),
    [t],
  );

  // The user name is built in the backend, this is only the preview.
  const uidVorschau = uidPreview(username);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const custom = role.startsWith("custom:");
    try {
      const r = await fetch("/api/admin/invites", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          kis_role: custom ? "custom" : role,
          custom_role_id: custom ? Number(role.slice("custom:".length)) : null,
          days: Number(days),
        }),
      });
      if (r.ok) {
        const resp = await r.json();
        setErstellt({ token: resp.token, uid: resp.uid, expires_at: resp.expires_at });
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

  function copyLink() {
    if (!erstellt) return;
    copyTextFromPromise(Promise.resolve(inviteUrl(window.location.origin, erstellt.token)));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border border-border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        {erstellt ? (
          <>
            <h2 className="text-lg font-semibold">{t("successTitle")}</h2>
            <p className="text-sm text-muted-soft">{t("successFor", { uid: erstellt.uid })}</p>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("linkLabel")}</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 min-w-0 truncate font-mono text-sm bg-surface border border-border rounded-md px-3 py-2 select-all">
                  {inviteUrl(window.location.origin, erstellt.token)}
                </code>
                <button
                  type="button"
                  onClick={copyLink}
                  className="px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap"
                >
                  {copied ? <Check size={16} weight="bold" /> : <Copy size={16} weight="bold" />}
                  {copied ? t("copied") : t("copy")}
                </button>
              </div>
            </div>

            <div className="flex items-start gap-2 bg-warn-bg text-warn-strong text-sm rounded-md px-3 py-2">
              <Warning size={18} weight="bold" className="mt-0.5 shrink-0" />
              <span>
                {t("warning", {
                  date: new Date(erstellt.expires_at).toLocaleDateString("de-DE", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  }),
                })}
              </span>
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
            <p className="text-xs text-muted-soft">{t("hint")}</p>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted" htmlFor="invite-username">
                {t("fieldUsername")}
              </label>
              <input
                id="invite-username"
                type="text"
                required
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
              />
              <p className="text-xs text-muted-soft">
                {uidVorschau ? t("uidHint", { uid: uidVorschau }) : t("usernameHint")}
              </p>
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("fieldRole")}</label>
              <Select value={role} onChange={setRole} options={roleOptions} className="w-full" />
            </div>

            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted">{t("fieldDays")}</label>
              <Select value={days} onChange={setDays} options={dayOptions} className="w-full" />
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
                disabled={submitting || !uidVorschau}
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
