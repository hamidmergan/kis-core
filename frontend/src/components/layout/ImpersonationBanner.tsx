"use client";

/** Bar above every page while somebody is logged in as this account. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { SignOut } from "@phosphor-icons/react";
import { checkAuthStatus, clearAuthCache, logout } from "@/lib/auth";
import type { Impersonator } from "@/types";

export default function ImpersonationBanner() {
  const t = useTranslations("impersonation");
  const [wer, setWer] = useState<Impersonator | null>(null);
  const [name, setName] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  useEffect(() => {
    checkAuthStatus()
      .then((s) => {
        if (!s.impersonator) return;
        setWer(s.impersonator);
        setName(s.display_name || s.username || "");
      })
      .catch(() => {});
  }, []);

  if (!wer) return null;

  async function zurueck() {
    setLaeuft(true);
    const res = await fetch("/api/admin/impersonation/stop", {
      method: "POST",
      credentials: "include",
    });
    clearAuthCache();
    if (res.ok) {
      // Hard nav so the server layout re-reads the swapped session cookie.
      window.location.assign("/admin/users/all");
      return;
    }
    // Own session gone, only a fresh login gets you out of here.
    await logout().catch(() => {});
    window.location.assign("/login");
  }

  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-center gap-3 px-4 py-2 text-sm"
      style={{ backgroundColor: "var(--warn-solid)", color: "var(--on-warn)" }}
    >
      <span className="font-medium">{t("banner", { name })}</span>
      <button
        type="button"
        onClick={zurueck}
        disabled={laeuft}
        className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 font-medium transition-opacity disabled:opacity-60"
        style={{ borderColor: "var(--on-warn)" }}
      >
        <SignOut size={14} weight="bold" />
        {laeuft ? t("backBusy") : t("back")}
      </button>
    </div>
  );
}
