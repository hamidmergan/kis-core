"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import { eventApi } from "@/lib/event/api";
import { TASK_IDS } from "@/lib/event/tasks";
import type { EventStats } from "@/lib/event/types";
import { BTN_SECONDARY } from "./fields";

/** Accounts per ticked task and how many finished the card. */
export default function TaskStatsCard() {
  const t = useTranslations("eventAdmin.tasks");
  const tt = useTranslations("eventTasks.tasks");
  const [stats, setStats] = useState<EventStats["tasks"] | null>(null);
  const [failed, setFailed] = useState(false);
  const [version, setVersion] = useState(0);
  const [reset, setReset] = useState<"idle" | "busy" | "done" | "failed">("idle");
  useEffect(() => {
    eventApi.adminStats().then((s) => setStats(s.tasks)).catch(() => setFailed(true));
  }, [version]);

  const resetOwn = () => {
    setReset("busy");
    eventApi
      .adminResetOwnTasks()
      .then(() => {
        setReset("done");
        setVersion((v) => v + 1);
      })
      .catch(() => setReset("failed"));
  };

  return (
    <SettingCard title={t("statsTitle")}>
      {failed && <p className="mt-4 text-sm text-error">{t("statsFailed")}</p>}
      {stats && (
        <ul className="mt-4 flex flex-col gap-1.5 text-sm" data-testid="task-stats">
          {TASK_IDS.map((id) => (
            <li key={id} className="flex justify-between gap-3">
              <span className="text-foreground">{tt(`${id}.title`)}</span>
              <span className="tabular-nums text-foreground-soft">{t("accounts", { n: stats.byTask[id] ?? 0 })}</span>
            </li>
          ))}
          <li className="flex justify-between gap-3 mt-2 font-semibold">
            <span>{t("complete")}</span>
            <span className="tabular-nums">{t("accounts", { n: stats.complete })}</span>
          </li>
        </ul>
      )}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button type="button" onClick={resetOwn} disabled={reset === "busy"} className={BTN_SECONDARY} data-testid="task-reset-own">
          {t("resetOwn")}
        </button>
        {reset === "done" && <span className="text-sm text-foreground-soft">{t("resetOwnDone")}</span>}
        {reset === "failed" && <span className="text-sm text-error">{t("resetOwnFailed")}</span>}
      </div>
      <p className="mt-2 text-xs text-muted">{t("resetOwnHint")}</p>
    </SettingCard>
  );
}
