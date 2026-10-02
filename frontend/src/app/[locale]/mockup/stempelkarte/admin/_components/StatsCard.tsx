"use client";

import { useTranslations } from "next-intl";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import { useMockup } from "../../../_lib/store";
import { useText2 } from "../../../_lib/useText2";

/** Sample numbers per stand as plain bars, nothing is measured in the mockup. */
export default function StatsCard() {
  const t = useTranslations("mockup.admin.stats");
  const ts = useTranslations("mockup.admin.stations");
  const text = useText2();
  const [config] = useMockup("config");
  const visits = config.stats.visitsByStation;
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
        <span className="font-semibold tabular-nums">{config.stats.completeCards}</span>
      </p>
    </SettingCard>
  );
}
