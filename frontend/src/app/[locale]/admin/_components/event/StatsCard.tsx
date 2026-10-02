"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import { useEventConfig } from "@/lib/event/adminStore";
import { eventApi } from "@/lib/event/api";
import type { EventStats } from "@/lib/event/types";
import { useText2 } from "@/lib/event/useText2";

/** Visitors per stand as plain bars, counted from the stamps on the server. */
export default function StatsCard() {
  const t = useTranslations("eventAdmin.stats");
  const ts = useTranslations("eventAdmin.stations");
  const text = useText2();
  const [config] = useEventConfig();
  const [stats, setStats] = useState<EventStats | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    eventApi.adminStats().then(setStats).catch(() => setFailed(true));
  }, []);
  if (failed) return <p className="text-sm text-error">{t("loadFailed")}</p>;
  if (!stats) return <p className="text-sm text-muted">{t("loading")}</p>;
  const visits = stats.visitsByStation;
  const max = Math.max(1, ...config.stations.map((s) => visits[s.id] ?? 0));

  return (
    <SettingCard title={t("title")} description={t("description")}>
      <p className="mt-4 text-xs font-medium text-muted">{t("perStation")}</p>
      {config.stations.length === 0 && <p className="mt-2 text-sm text-muted">{ts("empty")}</p>}
      <ul className="mt-2 flex flex-col gap-2" data-testid="stats-list">
        {config.stations.map((s) => {
          const n = visits[s.id] ?? 0;
          return (
            <li
              key={s.id}
              className="grid grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[minmax(0,12rem)_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1"
            >
              <span className="text-sm text-foreground truncate">{text(s.name)}</span>
              <div className="order-3 sm:order-2 col-span-2 sm:col-span-1 h-2.5 rounded-full bg-kb/10 overflow-hidden">
                <div className="h-full rounded-full bg-kb" style={{ width: `${Math.round((n / max) * 100)}%` }} />
              </div>
              <span className="order-2 sm:order-3 text-sm tabular-nums text-foreground-soft text-right whitespace-nowrap">
                {t("visitors", { n })}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-5 text-sm text-foreground">
        <span className="text-muted">{t("complete")}</span>{" "}
        <span className="font-semibold tabular-nums">{stats.completeCards}</span>
      </p>
    </SettingCard>
  );
}
