"use client";

/** The record of who was inside whose account. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { UserSwitch } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import { EmptyState } from "@/components/ui/EmptyState";

type Eintrag = {
  id: number;
  actor_username: string;
  target_username: string;
  started_at: string;
  ended_at: string | null;
  ended_reason: string | null;
};

function zeitpunkt(wert: string | null): string {
  if (!wert) return "";
  return new Date(wert).toLocaleString("de-DE");
}

export default function ImpersonationLogTab() {
  const t = useTranslations("admin.impersonationLog");
  const [eintraege, setEintraege] = useState<Eintrag[]>([]);
  const [loading, setLoading] = useState(true);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    fetch("/api/admin/impersonation/log?limit=200", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load"))))
      .then((d) => setEintraege(d.entries ?? []))
      .catch(() => setFehler(t("loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  function ende(e: Eintrag) {
    if (!e.ended_at) {
      return (
        <StatusMark tone="warn" className="text-xs">
          {t("running")}
        </StatusMark>
      );
    }
    const grund = e.ended_reason === "logout" ? t("reasonLogout") : t("reasonManual");
    return (
      <span className="whitespace-nowrap">
        {zeitpunkt(e.ended_at)} <span className="text-muted-soft">({grund})</span>
      </span>
    );
  }

  if (loading) return <Spinner className="flex justify-center py-12" />;
  if (fehler) return <StatusMark tone="error" className="text-sm">{fehler}</StatusMark>;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-soft">{t("hint")}</p>

      {eintraege.length === 0 ? (
        <EmptyState size="lg" icon={<UserSwitch size={32} weight="bold" />} text={t("empty")} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
            <thead className="bg-surface text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3 text-left">{t("colActor")}</th>
                <th className="px-4 py-3 text-left">{t("colTarget")}</th>
                <th className="px-4 py-3 text-left">{t("colStart")}</th>
                <th className="px-4 py-3 text-left">{t("colEnd")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft bg-background">
              {eintraege.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-3 font-medium text-foreground">{e.actor_username}</td>
                  <td className="px-4 py-3 text-foreground-soft">{e.target_username}</td>
                  <td className="px-4 py-3 text-muted-soft text-xs whitespace-nowrap">
                    {zeitpunkt(e.started_at)}
                  </td>
                  <td className="px-4 py-3 text-muted-soft text-xs">{ende(e)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
