"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";

export default function WhitelistTab({ adminEmail }: { adminEmail: string }) {
  const t = useTranslations("admin");
  const [emails, setEmails] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [newEmail, setNewEmail] = useState("");
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetch("/api/admin/whitelist", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setEmails(d.emails ?? []))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    if (!newEmail.trim()) return;
    setAdding(true);
    setError("");
    try {
      const res = await fetch("/api/admin/whitelist", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: newEmail.trim() }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || t("whitelist.addError"));
        return;
      }
      setEmails((prev) => [...prev, newEmail.trim().toLowerCase()]);
      setNewEmail("");
    } finally {
      setAdding(false);
    }
  };

  const remove = async (email: string) => {
    setRemoving(email);
    try {
      const res = await fetch(`/api/admin/whitelist/${encodeURIComponent(email)}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || t("whitelist.removeError"));
        return;
      }
      setEmails((prev) => prev.filter((e) => e !== email));
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="email"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder={t("whitelist.placeholder")}
          className="flex-1 text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <button
          onClick={add}
          disabled={adding || !newEmail.trim()}
          className="btn-primary px-4 py-2 text-sm font-medium rounded-md disabled:opacity-40"
        >
          {adding ? t("ellipsis") : t("whitelist.add")}
        </button>
      </div>
      {error && <p className="text-xs text-error">{error}</p>}

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : emails.length === 0 ? (
        <p className="text-sm text-muted-soft text-center py-8">{t("whitelist.empty")}</p>
      ) : (
        <ul className="divide-y divide-border-soft border border-border-soft rounded-xl overflow-hidden">
          {emails.map((email) => {
            const isAdmin = email.toLowerCase() === adminEmail.toLowerCase();
            return (
              <li
                key={email}
                className={`px-5 py-3 flex items-center justify-between gap-4 ${isAdmin ? "bg-surface" : "bg-background"}`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  {isAdmin && (
                    <svg
                      className="w-3.5 h-3.5 text-muted-soft shrink-0"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path d="M12 1a5 5 0 00-5 5v3H5a2 2 0 00-2 2v10a2 2 0 002 2h14a2 2 0 002-2V11a2 2 0 00-2-2h-2V6a5 5 0 00-5-5zm0 2a3 3 0 013 3v3H9V6a3 3 0 013-3zm0 10a2 2 0 110 4 2 2 0 010-4z" />
                    </svg>
                  )}
                  <span className={`text-sm truncate ${isAdmin ? "text-muted" : "text-foreground-soft"}`}>
                    {email}
                  </span>
                  {isAdmin && (
                    <span className="text-[10px] font-medium text-muted-soft bg-surface-dim px-1.5 py-0.5 rounded-full shrink-0">
                      {t("whitelist.adminBadge")}
                    </span>
                  )}
                </div>
                {isAdmin ? (
                  <span className="text-xs text-border shrink-0 cursor-default select-none">{t("whitelist.remove")}</span>
                ) : (
                  <button
                    onClick={() => remove(email)}
                    disabled={removing === email}
                    className="text-xs text-error hover:underline disabled:opacity-50 shrink-0"
                  >
                    {removing === email ? t("ellipsis") : t("whitelist.remove")}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
