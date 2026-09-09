"use client";

/** The open and used invitations. */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import type { StatusTone } from "@/lib/jobStatusDisplay";
import { copyTextFromPromise } from "@/lib/clipboard";
import CreateInviteDialog from "./CreateInviteDialog";
import { inviteUrl } from "./inviteUrl";

type Invite = {
  id: number;
  email: string;
  uid: string;
  role: string;
  custom_role_id: number | null;
  token: string;
  created_at: string;
  expires_at: string;
  used_at: string | null;
  status: "open" | "used" | "expired";
};

const TON: Record<Invite["status"], StatusTone> = {
  open: "brand",
  used: "success",
  expired: "muted",
};

function datum(wert: string): string {
  return new Date(wert).toLocaleDateString("de-DE");
}

export default function InvitesTab() {
  const t = useTranslations("admin.invites");
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [customRoles, setCustomRoles] = useState<{ id: number; name: string }[]>([]);
  const [dialogOffen, setDialogOffen] = useState(false);
  const [kopiert, setKopiert] = useState<number | null>(null);

  const laden = useCallback(() => {
    fetch("/api/admin/invites", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load"))))
      .then((d) => setInvites(d.invites ?? []))
      .catch(() => setError(t("loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(() => {
    laden();
    fetch("/api/admin/roles", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.custom_roles) setCustomRoles(d.custom_roles);
      })
      .catch(() => {});
  }, [laden]);

  function rollenName(e: Invite): string {
    if (e.role !== "custom") return e.role === "staff" ? t("roleStaff") : t("roleUser");
    return customRoles.find((r) => r.id === e.custom_role_id)?.name ?? t("roleUser");
  }

  function kopieren(invite: Invite) {
    copyTextFromPromise(Promise.resolve(inviteUrl(window.location.origin, invite.token)));
    setKopiert(invite.id);
    setTimeout(() => setKopiert(null), 1500);
  }

  async function zuruecknehmen(invite: Invite) {
    const r = await fetch(`/api/admin/invites/${invite.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!r.ok) {
      setError(t("withdrawError"));
      return;
    }
    setInvites((prev) => prev.filter((e) => e.id !== invite.id));
  }

  const offen = invites.filter((e) => e.status === "open").length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted-soft">
          {t("summary", { n: invites.length, offen })}
        </span>
        <button
          type="button"
          onClick={() => setDialogOffen(true)}
          className="px-3 py-2 text-sm btn-primary rounded-md transition-colors whitespace-nowrap"
        >
          {t("createButton")}
        </button>
      </div>

      {error && <p className="text-xs text-error">{error}</p>}

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : invites.length === 0 ? (
        <p className="text-sm text-muted-soft text-center py-8">{t("empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
            <thead className="bg-surface text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3 text-left">{t("colUsername")}</th>
                <th className="px-4 py-3 text-left">{t("colRole")}</th>
                <th className="px-4 py-3 text-left">{t("colCreated")}</th>
                <th className="px-4 py-3 text-left">{t("colExpires")}</th>
                <th className="px-4 py-3 text-left">{t("colStatus")}</th>
                <th className="px-4 py-3 text-left">{t("colActions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft bg-background">
              {invites.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-foreground">{e.uid}</p>
                  </td>
                  <td className="px-4 py-3 text-foreground-soft">{rollenName(e)}</td>
                  <td className="px-4 py-3 text-foreground-soft">{datum(e.created_at)}</td>
                  <td className="px-4 py-3 text-foreground-soft">{datum(e.expires_at)}</td>
                  <td className="px-4 py-3">
                    <StatusMark tone={TON[e.status]} className="text-xs">
                      {t(`status${e.status[0].toUpperCase()}${e.status.slice(1)}` as
                        "statusOpen" | "statusUsed" | "statusExpired")}
                    </StatusMark>
                  </td>
                  <td className="px-4 py-3">
                    {e.status === "open" ? (
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => kopieren(e)}
                          className="text-xs text-kb hover:underline flex items-center gap-1"
                        >
                          {kopiert === e.id ? <Check size={12} weight="bold" /> : <Copy size={12} weight="bold" />}
                          {kopiert === e.id ? t("copied") : t("copyLink")}
                        </button>
                        <button
                          type="button"
                          onClick={() => zuruecknehmen(e)}
                          className="text-xs text-error hover:underline"
                        >
                          {t("withdraw")}
                        </button>
                      </div>
                    ) : e.status === "used" ? (
                      <span className="text-xs text-muted-soft">
                        {t("usedOn", { date: datum(e.used_at ?? e.expires_at) })}
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => zuruecknehmen(e)}
                        className="text-xs text-error hover:underline"
                      >
                        {t("withdraw")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dialogOffen && (
        <CreateInviteDialog onClose={() => setDialogOffen(false)} onCreated={laden} />
      )}
    </div>
  );
}
